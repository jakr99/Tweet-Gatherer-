from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from research_agent.auto_label import DEFAULT_OPENAI_MODEL, OpenAIClassifier
from research_agent.balancer import balanced_target_met, high_confidence_case_counts
from research_agent.exporter import export_workbook
from research_agent.images import record_image_downloads
from research_agent.importer import read_import_file
from research_agent.labels import ALL_CASES, balance_rows, derive_case_label, incomplete_label_summary
from research_agent.models import Candidate
from research_agent.store import CandidateStore
from research_agent.x_api import (
    XApiClient,
    candidates_from_search_response,
    text_contains_required_term,
)


DEFAULT_DB = Path("data/research_agent.sqlite")
DEFAULT_EXPORT = Path("exports/candidates.xlsx")
DEFAULT_CONFIG = Path("config/queries.yaml")
NON_DISASTER_REQUIRED_TERMS = [
    "wildfire",
    "fire",
    "flood",
    "flooding",
    "hurricane",
    "earthquake",
    "tornado",
    "storm",
    "disaster",
    "evacuation",
    "emergency",
    "crisis",
    "drowning",
    "buried",
    "swamped",
    "meltdown",
    "surge",
]


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

    auto_label_parser = subparsers.add_parser(
        "auto-label",
        help="Use a multimodal OpenAI model to provisionally label candidates.",
    )
    auto_label_parser.add_argument("--limit", type=int, default=50)
    auto_label_parser.add_argument("--min-confidence", type=float, default=0.65)
    auto_label_parser.add_argument("--relabel", action="store_true")

    collect_balanced_parser = subparsers.add_parser(
        "collect-balanced",
        help="Collect, download, auto-label, and export until target buckets are filled.",
    )
    collect_balanced_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    collect_balanced_parser.add_argument("--target-per-case", type=int, default=12)
    collect_balanced_parser.add_argument("--max-rounds", type=int, default=5)
    collect_balanced_parser.add_argument("--limit-per-query", type=int, default=100)
    collect_balanced_parser.add_argument("--min-confidence", type=float, default=0.65)
    collect_balanced_parser.add_argument("--output", default=str(DEFAULT_EXPORT))

    fill_balanced_parser = subparsers.add_parser(
        "fill-balanced",
        help="Collect, label, and cap candidates until every target bucket is filled.",
    )
    fill_balanced_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    fill_balanced_parser.add_argument("--target-per-case", type=int, default=50)
    fill_balanced_parser.add_argument("--max-rounds", type=int, default=20)
    fill_balanced_parser.add_argument("--limit-per-query", type=int, default=50)
    fill_balanced_parser.add_argument("--min-confidence", type=float, default=0.65)
    fill_balanced_parser.add_argument("--output", default=str(DEFAULT_EXPORT))

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

    if args.command == "auto-label":
        store.initialize()
        labeled, failed = _auto_label_candidates(
            store,
            limit=args.limit,
            relabel=args.relabel,
        )
        print(f"Auto-labeled {labeled} candidates; {failed} failed")
        return 1 if failed else 0

    if args.command == "collect-balanced":
        store.initialize()
        return _collect_balanced(
            store=store,
            workspace=workspace,
            config_path=args.config,
            target_per_case=args.target_per_case,
            max_rounds=args.max_rounds,
            limit_per_query=args.limit_per_query,
            min_confidence=args.min_confidence,
            output_path=args.output,
        )

    if args.command == "fill-balanced":
        store.initialize()
        return _fill_balanced(
            store=store,
            workspace=workspace,
            config_path=args.config,
            target_per_case=args.target_per_case,
            max_rounds=args.max_rounds,
            limit_per_query=args.limit_per_query,
            min_confidence=args.min_confidence,
            output_path=args.output,
        )

    if args.command == "balance":
        store.initialize()
        candidates = store.list_candidates()
        for row in balance_rows(candidates):
            print(
                f"{row['case_label']}: total={row['total']} "
                f"candidate={row['candidate']} needs_review={row['needs_review']} "
                f"accepted={row['accepted']} rejected={row['rejected']}"
            )
        summary = incomplete_label_summary(candidates)
        print(
            f"{summary['case_label']}: total={summary['total']} "
            f"candidate={summary['candidate']} needs_review={summary['needs_review']} "
            f"accepted={summary['accepted']} rejected={summary['rejected']} "
            f"unknown_text={summary['unknown_text_label']} "
            f"unknown_image={summary['unknown_image_label']} "
            f"unknown_disaster={summary['unknown_disaster_label']}"
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
    pagination_tokens: dict[str, str] | None = None,
    active_case_labels: set[str] | None = None,
) -> tuple[int, int]:
    config = _load_yaml(_resolve(workspace, config_path))
    client = XApiClient()
    total = 0
    failed = 0
    for query_config in config.get("queries", []):
        name = query_config["name"]
        if not _query_targets_active(query_config, active_case_labels):
            continue
        if pagination_tokens is not None and pagination_tokens.get(name) == "":
            continue
        query = query_config["query"]
        seed_labels = query_config.get("seed_labels", {})
        required_terms = query_config.get("required_terms", [])
        next_token = pagination_tokens.get(name) if pagination_tokens is not None else None
        started = datetime.now(UTC).isoformat()
        error = ""
        candidates = []
        try:
            if next_token:
                payload = client.search_recent(query, max_results=limit, next_token=next_token)
            else:
                payload = client.search_recent(query, max_results=limit)
            if pagination_tokens is not None:
                pagination_tokens[name] = payload.get("meta", {}).get("next_token", "")
            candidates = candidates_from_search_response(payload, name, query, seed_labels)
            candidates = _filter_by_required_terms(candidates, seed_labels, required_terms)
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


def _query_targets_active(
    query_config: dict[str, Any],
    active_case_labels: set[str] | None,
) -> bool:
    if active_case_labels is None:
        return True
    target_cases = set(query_config.get("target_cases", []))
    if not target_cases:
        return True
    return bool(target_cases & active_case_labels)


def _filter_by_required_terms(
    candidates: list[Candidate],
    seed_labels: dict[str, str],
    required_terms: list[str],
) -> list[Candidate]:
    if seed_labels.get("disaster_label") != "not_real_disaster" or not required_terms:
        return candidates
    return [
        candidate
        for candidate in candidates
        if text_contains_required_term(candidate.tweet_text, required_terms)
    ]


def _auto_label_candidates(
    store: CandidateStore,
    limit: int,
    relabel: bool = False,
) -> tuple[int, int]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is required for auto-label.", file=sys.stderr)
        return 0, 1
    model = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    classifier = OpenAIClassifier(api_key=api_key, model=model)
    candidates = (
        store.list_candidates()[:limit]
        if relabel
        else store.list_candidates_needing_labels(limit)
    )
    labeled = 0
    failed = 0
    skipped = 0
    if candidates:
        print(f"Auto-labeling {len(candidates)} candidates")
    for index, candidate in enumerate(candidates, start=1):
        print(f"Labeling {index}/{len(candidates)}: {candidate.tweet_id}/{candidate.image_id}", flush=True)
        if not candidate.image_path and not candidate.image_url:
            skipped += 1
            continue
        try:
            result = classifier.classify(candidate)
            store.update_candidate_labels(
                tweet_id=candidate.tweet_id,
                image_id=candidate.image_id,
                text_label=result.text_label,
                image_label=result.image_label,
                disaster_label=result.disaster_label,
                text_confidence=result.text_confidence,
                image_confidence=result.image_confidence,
                disaster_confidence=result.disaster_confidence,
                label_explanation=result.explanation,
                label_model=model,
                labeled_at=datetime.now(UTC).isoformat(),
            )
            labeled += 1
        except Exception as exc:  # noqa: BLE001 - row-level model failures should be visible
            failed += 1
            print(
                f"Auto-label failed for {candidate.tweet_id}/{candidate.image_id}: {exc}",
                file=sys.stderr,
            )
    if skipped:
        print(f"Skipped {skipped} candidates without images")
    return labeled, failed


def _collect_balanced(
    store: CandidateStore,
    workspace: Path,
    config_path: str,
    target_per_case: int,
    max_rounds: int,
    limit_per_query: int,
    min_confidence: float,
    output_path: str,
) -> int:
    any_failed = False
    for round_number in range(1, max_rounds + 1):
        print(f"Balanced collection round {round_number}/{max_rounds}")
        _, collect_failed = _collect_from_config(
            store,
            workspace,
            config_path,
            limit_per_query,
        )
        downloaded, download_failed = record_image_downloads(store, _resolve(workspace, "data/images"))
        print(f"Downloaded {downloaded} images; {download_failed} failed")
        labeled, label_failed = _auto_label_candidates(
            store,
            limit=limit_per_query * 10,
            relabel=False,
        )
        print(f"Auto-labeled {labeled} candidates; {label_failed} failed")
        any_failed = any_failed or bool(collect_failed or label_failed)
        counts = high_confidence_case_counts(store.list_candidates(), min_confidence)
        for case_label, count in counts.items():
            print(f"{case_label}: {count}/{target_per_case}")
        if balanced_target_met(counts, target_per_case):
            print("Balanced target reached.")
            break
    export_path = export_workbook(store, _resolve(workspace, output_path))
    print(f"Exported workbook to {export_path}")
    return 1 if any_failed else 0


def _fill_balanced(
    store: CandidateStore,
    workspace: Path,
    config_path: str,
    target_per_case: int,
    max_rounds: int,
    limit_per_query: int,
    min_confidence: float,
    output_path: str,
) -> int:
    any_failed = False
    pagination_tokens: dict[str, str] = {}

    for round_number in range(1, max_rounds + 1):
        counts = _complete_case_counts(store.list_candidates())
        active_case_labels = _underfilled_case_labels(counts, target_per_case)
        if balanced_target_met(counts, target_per_case):
            print("Balanced target reached.")
            break

        print(f"Balanced fill round {round_number}/{max_rounds}")
        print(f"Collecting for {len(active_case_labels)} underfilled buckets")
        _, collect_failed = _collect_from_config(
            store,
            workspace,
            config_path,
            limit_per_query,
            pagination_tokens=pagination_tokens,
            active_case_labels=active_case_labels,
        )
        downloaded, download_failed = record_image_downloads(store, _resolve(workspace, "data/images"))
        print(f"Downloaded {downloaded} images; {download_failed} failed")
        unlabeled_count = _count_unlabeled_candidates(store)
        labeled, label_failed = _auto_label_candidates(
            store,
            limit=unlabeled_count,
            relabel=False,
        )
        print(f"Auto-labeled {labeled} candidates; {label_failed} failed")
        removed_non_disaster = _remove_non_disaster_without_terms(store)
        if removed_non_disaster:
            print(
                "Removed "
                f"{removed_non_disaster} non-disaster candidates without disaster terms"
            )
        removed = _enforce_balanced_target(store, target_per_case, min_confidence)
        if removed:
            print(f"Removed {removed} candidates outside the balanced target")
        any_failed = any_failed or bool(collect_failed or label_failed)

        counts = _complete_case_counts(store.list_candidates())
        for case_label, count in counts.items():
            print(f"{case_label}: {count}/{target_per_case}")
        if balanced_target_met(counts, target_per_case):
            print("Balanced target reached.")
            break

    final_counts = _complete_case_counts(store.list_candidates())
    removed_unlabeled = _remove_unlabeled_candidates(store)
    if removed_unlabeled:
        print(f"Removed {removed_unlabeled} unlabeled candidates before export")
    export_path = export_workbook(store, _resolve(workspace, output_path))
    print(f"Exported workbook to {export_path}")
    if not balanced_target_met(final_counts, target_per_case):
        print(
            "Balanced target not reached. Rerun the command to continue filling buckets.",
            file=sys.stderr,
        )
        return 1
    return 1 if any_failed else 0


def _remove_non_disaster_without_terms(store: CandidateStore) -> int:
    candidates = [
        candidate
        for candidate in store.list_candidates()
        if candidate.disaster_label == "not_real_disaster"
        and not text_contains_required_term(
            candidate.tweet_text,
            NON_DISASTER_REQUIRED_TERMS,
        )
    ]
    return store.delete_candidates(
        [(candidate.tweet_id, candidate.image_id) for candidate in candidates]
    )


def _complete_case_counts(candidates: list[Candidate]) -> dict[str, int]:
    counts = {case_label: 0 for case_label in ALL_CASES}
    for candidate in candidates:
        case_label = _candidate_case_label(candidate)
        if case_label in counts:
            counts[case_label] += 1
    return counts


def _count_unlabeled_candidates(store: CandidateStore) -> int:
    return sum(
        1
        for candidate in store.list_candidates()
        if _candidate_case_label(candidate) == "unknown"
    )


def _remove_unlabeled_candidates(store: CandidateStore) -> int:
    candidates = [
        candidate
        for candidate in store.list_candidates()
        if _candidate_case_label(candidate) == "unknown"
    ]
    return store.delete_candidates(
        [(candidate.tweet_id, candidate.image_id) for candidate in candidates]
    )


def _underfilled_case_labels(
    counts: dict[str, int],
    target_per_case: int,
) -> set[str]:
    return {
        case_label
        for case_label in ALL_CASES
        if counts.get(case_label, 0) < target_per_case
    }


def _enforce_balanced_target(
    store: CandidateStore,
    target_per_case: int,
    min_confidence: float,
) -> int:
    removals = _candidates_outside_balanced_target(
        store.list_candidates(),
        target_per_case,
        min_confidence,
    )
    return store.delete_candidates(
        [(candidate.tweet_id, candidate.image_id) for candidate in removals]
    )


def _candidates_outside_balanced_target(
    candidates: list[Candidate],
    target_per_case: int,
    min_confidence: float,
) -> list[Candidate]:
    removals: list[Candidate] = []
    grouped = {case_label: [] for case_label in ALL_CASES}

    for candidate in candidates:
        case_label = _candidate_case_label(candidate)
        if case_label not in grouped:
            continue
        grouped[case_label].append(candidate)

    for case_candidates in grouped.values():
        case_candidates.sort(key=_balanced_keep_sort_key)
        removals.extend(case_candidates[target_per_case:])
    return removals


def _candidate_case_label(candidate: Candidate) -> str:
    if candidate.case_label and candidate.case_label != "unknown":
        return candidate.case_label
    return derive_case_label(
        candidate.text_label,
        candidate.image_label,
        candidate.disaster_label,
    )


def _candidate_min_confidence(candidate: Candidate) -> float:
    return min(
        candidate.text_confidence,
        candidate.image_confidence,
        candidate.disaster_confidence,
    )


def _balanced_keep_sort_key(candidate: Candidate) -> tuple[float, str, str, str]:
    return (
        -_candidate_min_confidence(candidate),
        candidate.collected_at,
        candidate.tweet_id,
        candidate.image_id,
    )


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
    target_cases:
      - literal_text__literal_image__real_disaster
    seed_labels:
      disaster_label: real_disaster
  - name: flood_real_disaster_images
    query: '(flood OR flooding OR flashflood) has:images lang:en -is:retweet'
    target_cases:
      - literal_text__literal_image__real_disaster
    seed_labels:
      disaster_label: real_disaster
  - name: non_disaster_figurative_images
    query: '("storm of" OR "flood of" OR "on fire") has:images lang:en -is:retweet'
    target_cases:
      - figurative_text__literal_image__not_real_disaster
      - figurative_text__figurative_image__not_real_disaster
    required_terms:
      - storm
      - flood
      - fire
    seed_labels:
      disaster_label: not_real_disaster
"""


if __name__ == "__main__":
    raise SystemExit(main())
