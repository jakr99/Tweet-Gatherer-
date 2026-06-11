from __future__ import annotations

from collections.abc import Iterable

from research_agent.models import Candidate


ALL_CASES = [
    "literal_text__literal_image__real_disaster",
    "literal_text__figurative_image__real_disaster",
    "figurative_text__literal_image__real_disaster",
    "figurative_text__figurative_image__real_disaster",
    "literal_text__literal_image__not_real_disaster",
    "literal_text__figurative_image__not_real_disaster",
    "figurative_text__literal_image__not_real_disaster",
    "figurative_text__figurative_image__not_real_disaster",
]


def derive_case_label(text_label: str, image_label: str, disaster_label: str) -> str:
    if "unknown" in {text_label, image_label, disaster_label}:
        return "unknown"
    return f"{text_label}_text__{image_label}_image__{disaster_label}"


def normalize_candidate_case(candidate: Candidate) -> Candidate:
    candidate.case_label = derive_case_label(
        candidate.text_label,
        candidate.image_label,
        candidate.disaster_label,
    )
    return candidate


def balance_rows(candidates: Iterable[Candidate]) -> list[dict[str, int | str]]:
    rows = {
        case_label: {
            "case_label": case_label,
            "total": 0,
            "candidate": 0,
            "needs_review": 0,
            "accepted": 0,
            "rejected": 0,
        }
        for case_label in ALL_CASES
    }

    for candidate in candidates:
        case_label = candidate.case_label
        if not case_label or case_label == "unknown":
            case_label = derive_case_label(
                candidate.text_label,
                candidate.image_label,
                candidate.disaster_label,
            )
        if case_label not in rows:
            continue
        rows[case_label]["total"] += 1
        rows[case_label][candidate.review_status] += 1

    return [rows[case_label] for case_label in ALL_CASES]


def incomplete_label_summary(candidates: Iterable[Candidate]) -> dict[str, int | str]:
    summary = {
        "case_label": "incomplete_or_unknown_labels",
        "total": 0,
        "candidate": 0,
        "needs_review": 0,
        "accepted": 0,
        "rejected": 0,
        "unknown_text_label": 0,
        "unknown_image_label": 0,
        "unknown_disaster_label": 0,
    }
    for candidate in candidates:
        if derive_case_label(
            candidate.text_label,
            candidate.image_label,
            candidate.disaster_label,
        ) != "unknown":
            continue
        summary["total"] += 1
        summary[candidate.review_status] += 1
        if candidate.text_label == "unknown":
            summary["unknown_text_label"] += 1
        if candidate.image_label == "unknown":
            summary["unknown_image_label"] += 1
        if candidate.disaster_label == "unknown":
            summary["unknown_disaster_label"] += 1
    return summary
