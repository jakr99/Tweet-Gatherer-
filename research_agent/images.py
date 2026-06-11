from __future__ import annotations

import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

from research_agent.http import ssl_context
from research_agent.models import Candidate
from research_agent.store import CandidateStore


Downloader = Callable[[str], bytes | None]


def image_path_for_candidate(candidate: Candidate, image_root: str | Path) -> Path:
    image_root = Path(image_root)
    parsed = urllib.parse.urlparse(candidate.image_url)
    suffix = Path(parsed.path).suffix or ".jpg"
    return image_root / candidate.tweet_id / f"{candidate.image_id}{suffix}"


def default_downloader(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "research-agent/0.1"})
    with urllib.request.urlopen(request, timeout=30, context=ssl_context()) as response:
        return response.read()


def record_image_downloads(
    store: CandidateStore,
    image_root: str | Path = "data/images",
    downloader: Downloader = default_downloader,
) -> tuple[int, int]:
    downloaded = 0
    failed = 0
    for candidate in store.list_candidates():
        if not candidate.image_url:
            store.update_image_result(
                candidate.tweet_id,
                candidate.image_id,
                download_error="No image URL available",
            )
            failed += 1
            continue
        path = image_path_for_candidate(candidate, image_root)
        try:
            content = downloader(candidate.image_url)
            if not content:
                raise RuntimeError("No bytes returned for image URL")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            store.update_image_result(candidate.tweet_id, candidate.image_id, str(path))
            downloaded += 1
        except Exception as exc:  # noqa: BLE001 - row-level failure should not stop batch
            store.update_image_result(
                candidate.tweet_id,
                candidate.image_id,
                download_error=str(exc),
            )
            failed += 1
    return downloaded, failed
