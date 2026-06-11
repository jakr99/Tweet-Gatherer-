from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from research_agent.http import ssl_context
from research_agent.models import Candidate


RECENT_SEARCH_URL = "https://api.x.com/2/tweets/search/recent"
TWEET_LOOKUP_URL = "https://api.x.com/2/tweets"


@dataclass(slots=True)
class XApiClient:
    bearer_token: str | None = None

    def __post_init__(self) -> None:
        if self.bearer_token is None:
            self.bearer_token = os.environ.get("X_BEARER_TOKEN")

    def recent_search_params(self, query: str, max_results: int = 100) -> dict[str, str]:
        return {
            "query": query,
            "max_results": str(max_results),
            "tweet.fields": "attachments,author_id,created_at,text",
            "expansions": "attachments.media_keys",
            "media.fields": "media_key,type,url,preview_image_url,width,height",
        }

    def search_recent(self, query: str, max_results: int = 100) -> dict[str, Any]:
        params = self.recent_search_params(query, max_results=max_results)
        return self._get_json(RECENT_SEARCH_URL, params)

    def hydrate_tweets(self, tweet_ids: list[str]) -> dict[str, Any]:
        params = {
            "ids": ",".join(tweet_ids),
            "tweet.fields": "attachments,author_id,created_at,text",
            "expansions": "attachments.media_keys",
            "media.fields": "media_key,type,url,preview_image_url,width,height",
        }
        return self._get_json(TWEET_LOOKUP_URL, params)

    def _get_json(self, url: str, params: Mapping[str, str]) -> dict[str, Any]:
        if not self.bearer_token:
            raise RuntimeError("X_BEARER_TOKEN is required for X API commands.")
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            f"{url}?{query}",
            headers={"Authorization": f"Bearer {self.bearer_token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=30,
                context=ssl_context(),
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"X API request failed with HTTP {exc.code}: {detail}") from exc


def candidates_from_search_response(
    payload: Mapping[str, Any],
    source_query_name: str,
    source_query: str,
    seed_labels: Mapping[str, str] | None = None,
) -> list[Candidate]:
    seed_labels = seed_labels or {}
    media_by_key = {
        media.get("media_key"): media
        for media in payload.get("includes", {}).get("media", [])
        if media.get("media_key")
    }
    candidates: list[Candidate] = []

    for tweet in payload.get("data", []):
        media_keys = tweet.get("attachments", {}).get("media_keys", [])
        for media_key in media_keys:
            media = media_by_key.get(media_key)
            if not media or media.get("type") != "photo":
                continue
            image_url = media.get("url") or media.get("preview_image_url") or ""
            candidates.append(
                Candidate(
                    tweet_id=str(tweet.get("id", "")),
                    image_id=str(media_key),
                    tweet_text=tweet.get("text", ""),
                    image_url=image_url,
                    text_label=seed_labels.get("text_label", "unknown"),
                    image_label=seed_labels.get("image_label", "unknown"),
                    disaster_label=seed_labels.get("disaster_label", "unknown"),
                    review_status=seed_labels.get("review_status", "candidate"),
                    source="x_api",
                    source_query=source_query_name,
                    notes=f"query={source_query}",
                    author_id=str(tweet.get("author_id", "")),
                    created_at=tweet.get("created_at", ""),
                    media_type=media.get("type", ""),
                )
            )

    return candidates
