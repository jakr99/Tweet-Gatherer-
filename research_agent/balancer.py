from __future__ import annotations

from collections.abc import Mapping

from research_agent.labels import ALL_CASES, derive_case_label
from research_agent.models import Candidate


def high_confidence_case_counts(
    candidates: list[Candidate],
    min_confidence: float,
) -> dict[str, int]:
    counts = {case_label: 0 for case_label in ALL_CASES}
    for candidate in candidates:
        case_label = candidate.case_label
        if not case_label or case_label == "unknown":
            case_label = derive_case_label(
                candidate.text_label,
                candidate.image_label,
                candidate.disaster_label,
            )
        if case_label not in counts:
            continue
        if min(
            candidate.text_confidence,
            candidate.image_confidence,
            candidate.disaster_confidence,
        ) < min_confidence:
            continue
        counts[case_label] += 1
    return counts


def balanced_target_met(
    counts: Mapping[str, int],
    target_per_case: int,
) -> bool:
    return all(count >= target_per_case for count in counts.values())
