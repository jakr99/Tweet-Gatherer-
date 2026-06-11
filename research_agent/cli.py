from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from research_agent.exporter import export_workbook
from research_agent.images import record_image_downloads
from research_agent.importer import read_import_file
from research_agent.labels import balance_rows
from research_agent.models import Candidate
from research_agent.store import CandidateStore
from research_agent.x_api import XApiClient, candidates_from_search_response


DEFAULT_DB = Path("data/research_agent.sqlite")
DEFAULT_EXPORT = Path("exports/candidates.xlsx")
DEFAULT_CONFIG = Path("config/queries.yaml")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="research-agent")
    parser.add_argument(
        "--workspace",
        default=".",
        help="Project workspace containing config, data, images, and exports.",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="SQLite database path, relative to workspace unless absolute.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Create local folders, database, and starter config.")

    import_parser = subparsers.add_parser("import", help="Import tweet IDs or URLs.")
    import_parser.add_argument("path", help="CSV or text file containing tweet IDs/URLs.")

    collect_parser = subparsers.add_parser("collect", help="Collect candidates through X API.")
    collect_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    collect_parser.add_argument("--limit", type=int, default=100)

    download_parser = subparsers.add_parser("download-images", help="Download image media.")
    download_parser.add_argument("--image-root", default="data/images")

    export_parser = subparsers.add_parser("export", help="Export Excel workbook.")
    export_parser.add_argument("--output", default=str(DEFAULT_EXPORT))

    subparsers.add_parser("balance", help="Print balance counts for the eight target cells.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    workspace = Path(args.workspace)
    _load_dotenv(workspace / ".env")
    db_path = _resolve(workspace, args.db)
    store = CandidateStore(db_path)

    if args.command == "init":
        _init_workspace(workspace, store)
        print(f"Initialized research agent workspace at {workspace}")
        return 0

    if args.command == "import":
        store.initialize()
        import_path = Path(args.path)
        if not import_path.exists():
            print(f"Import file not found: {import_path}", file=sys.stderr)
            return 1
        tweet_ids = read_import_file(import_path)
        for tweet_id in tweet_ids:
            store.upsert_candidate(
                Candidate(
                    tweet_id=tweet_id,
                    image_id=f"imported:{tweet_id}",
                    source="import",
                    notes="Imported reference; hydrate with X API for full metadata.",
                )
            )
        print(f"Imported {len(tweet_ids)} candidate references")
        return 0

    if args.command == "collect":
        store.initialize()
        count, failed = _collect_from_config(store, workspace, args.config, args.limit)
        print(f"Collected {count} tweet-image candidates")
        return 1 if failed else 0

    if args.command == "download-images":
        store.initialize()
        downloaded, failed = record_image_downloads(
            store,
            _resolve(workspace, args.image_root),
        )
        print(f"Downloaded {downloaded} images; {failed} failed")
        return 0

    if args.command == "export":
        store.initialize()
        output_path = export_workbook(store, _resolve(workspace, args.output))
        print(f"Exported workbook to {output_path}")
        return 0

    if args.command == "balance":
        store.initialize()
        for row in balance_rows(store.list_candidates()):
            print(
                f"{row['case_label']}: total={row['total']} "
                f"candidate={row['candidate']} needs_review={row['needs_review']} "
                f"accepted={row['accepted']} rejected={row['rejected']}"
            )
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def _init_workspace(workspace: Path, store: CandidateStore) -> None:
    for directory in ["config", "data/images", "exports"]:
        (workspace / directory).mkdir(parents=True, exist_ok=True)
    store.initialize()
    config_path = workspace / DEFAULT_CONFIG
    if not config_path.exists():
        source = Path(__file__).resolve().parent.parent / "config" / "queries.yaml"
        if source.exists():
            shutil.copyfile(source, config_path)
        else:
            config_path.write_text(_starter_queries(), encoding="utf-8")


def _collect_from_config(
    store: CandidateStore,
    workspace: Path,
    config_path: str,
    limit: int,
) -> tuple[int, int]:
    config = _load_yaml(_resolve(workspace, config_path))
    client = XApiClient()
    total = 0
    failed = 0
    for query_config in config.get("queries", []):
        name = query_config["name"]
        query = query_config["query"]
        seed_labels = query_config.get("seed_labels", {})
        started = datetime.now(UTC).isoformat()
        error = ""
        candidates = []
        try:
            payload = client.search_recent(query, max_results=limit)
            candidates = candidates_from_search_response(payload, name, query, seed_labels)
            for candidate in candidates:
                store.upsert_candidate(candidate)
        except Exception as exc:  # noqa: BLE001 - record run-level API failure
            error = str(exc)
            failed += 1
            if _is_credits_depleted_error(error):
                print(
                    "X API credits are depleted for this bearer token/account. "
                    "Collection cannot continue until X API credits or access are restored.",
                    file=sys.stderr,
                )
            else:
                print(f"Collection failed for {name}: {error}", file=sys.stderr)
        finished = datetime.now(UTC).isoformat()
        store.add_collection_run("x_api", name, started, finished, len(candidates), error)
        total += len(candidates)
        if _is_credits_depleted_error(error):
            break
    return total, failed


def _resolve(workspace: Path, path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return workspace / path


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _is_credits_depleted_error(error: str) -> bool:
    return "CreditsDepleted" in error or "does not have any credits" in error


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _starter_queries() -> str:
    return """queries:
  - name: wildfire_real_disaster_images
    query: '(wildfire OR fire OR evacuation) has:images lang:en -is:retweet'
    seed_labels:
      disaster_label: real_disaster
  - name: flood_real_disaster_images
    query: '(flood OR flooding OR flashflood) has:images lang:en -is:retweet'
    seed_labels:
      disaster_label: real_disaster
  - name: non_disaster_figurative_images
    query: '("storm of" OR "flood of" OR "on fire") has:images lang:en -is:retweet'
    seed_labels:
      disaster_label: not_real_disaster
"""


if __name__ == "__main__":
    raise SystemExit(main())
