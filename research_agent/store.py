from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from research_agent.labels import normalize_candidate_case
from research_agent.models import Candidate


CANDIDATE_COLUMNS = [
    "tweet_id",
    "image_id",
    "tweet_text",
    "image_url",
    "image_path",
    "text_label",
    "image_label",
    "disaster_label",
    "case_label",
    "review_status",
    "source",
    "source_query",
    "collected_at",
    "notes",
    "author_id",
    "created_at",
    "media_type",
    "download_error",
]


class CandidateStore:
    def __init__(self, db_path: str | Path = "data/research_agent.sqlite") -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute(
                """
                create table if not exists candidates (
                    tweet_id text not null,
                    image_id text not null,
                    tweet_text text not null default '',
                    image_url text not null default '',
                    image_path text not null default '',
                    text_label text not null default 'unknown',
                    image_label text not null default 'unknown',
                    disaster_label text not null default 'unknown',
                    case_label text not null default 'unknown',
                    review_status text not null default 'candidate',
                    source text not null default '',
                    source_query text not null default '',
                    collected_at text not null default '',
                    notes text not null default '',
                    author_id text not null default '',
                    created_at text not null default '',
                    media_type text not null default '',
                    download_error text not null default '',
                    primary key (tweet_id, image_id)
                )
                """
            )
            connection.execute(
                """
                create table if not exists collection_runs (
                    id integer primary key autoincrement,
                    source text not null,
                    source_query text not null,
                    started_at text not null,
                    finished_at text not null,
                    result_count integer not null,
                    error text not null default ''
                )
                """
            )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def upsert_candidate(self, candidate: Candidate) -> None:
        self.initialize()
        normalize_candidate_case(candidate)
        values = [getattr(candidate, column) for column in CANDIDATE_COLUMNS]
        assignments = ", ".join(
            f"{column}=excluded.{column}"
            for column in CANDIDATE_COLUMNS
            if column not in {"tweet_id", "image_id"}
        )
        placeholders = ", ".join("?" for _ in CANDIDATE_COLUMNS)
        with self.connect() as connection:
            connection.execute(
                f"""
                insert into candidates ({", ".join(CANDIDATE_COLUMNS)})
                values ({placeholders})
                on conflict(tweet_id, image_id) do update set {assignments}
                """,
                values,
            )

    def list_candidates(self) -> list[Candidate]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                f"select {', '.join(CANDIDATE_COLUMNS)} from candidates order by tweet_id, image_id"
            ).fetchall()
        return [self._candidate_from_row(row) for row in rows]

    def update_image_result(
        self,
        tweet_id: str,
        image_id: str,
        image_path: str = "",
        download_error: str = "",
    ) -> None:
        self.initialize()
        with self.connect() as connection:
            connection.execute(
                """
                update candidates
                set image_path = ?, download_error = ?
                where tweet_id = ? and image_id = ?
                """,
                (image_path, download_error, tweet_id, image_id),
            )

    def add_collection_run(
        self,
        source: str,
        source_query: str,
        started_at: str,
        finished_at: str,
        result_count: int,
        error: str = "",
    ) -> None:
        self.initialize()
        with self.connect() as connection:
            connection.execute(
                """
                insert into collection_runs
                (source, source_query, started_at, finished_at, result_count, error)
                values (?, ?, ?, ?, ?, ?)
                """,
                (source, source_query, started_at, finished_at, result_count, error),
            )

    def list_collection_runs(self) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                """
                select source, source_query, started_at, finished_at, result_count, error
                from collection_runs
                order by id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _candidate_from_row(row: sqlite3.Row) -> Candidate:
        return Candidate(**{column: row[column] for column in CANDIDATE_COLUMNS})
