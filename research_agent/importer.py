from __future__ import annotations

import csv
import re
from pathlib import Path


TWEET_URL_RE = re.compile(r"(?:x|twitter)\.com/[^/]+/status/(\d+)")
RAW_ID_RE = re.compile(r"^\d+$")


def parse_tweet_reference(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    url_match = TWEET_URL_RE.search(value)
    if url_match:
        return url_match.group(1)
    if RAW_ID_RE.match(value):
        return value
    return None


def read_import_file(path: str | Path) -> list[str]:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return _read_csv_import(path)
    return _read_text_import(path)


def _read_text_import(path: Path) -> list[str]:
    tweet_ids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        tweet_id = parse_tweet_reference(line)
        if tweet_id:
            tweet_ids.append(tweet_id)
    return tweet_ids


def _read_csv_import(path: Path) -> list[str]:
    tweet_ids: list[str] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            values = [
                row.get("tweet_id", ""),
                row.get("tweet_url", ""),
                row.get("url", ""),
                row.get("id", ""),
            ]
            tweet_id = next(
                (
                    parsed
                    for parsed in (parse_tweet_reference(value) for value in values)
                    if parsed
                ),
                None,
            )
            if tweet_id:
                tweet_ids.append(tweet_id)
    return tweet_ids
