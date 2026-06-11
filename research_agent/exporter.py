from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from research_agent.labels import balance_rows, incomplete_label_summary
from research_agent.store import CANDIDATE_COLUMNS, CandidateStore
from research_agent.xlsx import write_workbook


def export_workbook(store: CandidateStore, output_path: str | Path) -> Path:
    candidates = store.list_candidates()
    candidate_rows = [asdict(candidate) for candidate in candidates]
    if not candidate_rows:
        candidate_rows = [{column: "" for column in CANDIDATE_COLUMNS}]
    sheets = {
        "candidates": candidate_rows,
        "balance_summary": balance_rows(candidates) + [incomplete_label_summary(candidates)],
        "collection_runs": store.list_collection_runs()
        or [
            {
                "source": "",
                "source_query": "",
                "started_at": "",
                "finished_at": "",
                "result_count": 0,
                "error": "",
            }
        ],
    }
    write_workbook(output_path, sheets)
    return Path(output_path)
