from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


TEXT_LABELS = {"literal", "figurative", "unknown"}
IMAGE_LABELS = {"literal", "figurative", "unknown"}
DISASTER_LABELS = {"real_disaster", "not_real_disaster", "unknown"}
REVIEW_STATUSES = {"candidate", "needs_review", "accepted", "rejected"}


@dataclass(slots=True)
class Candidate:
    tweet_id: str
    image_id: str
    tweet_text: str = ""
    image_url: str = ""
    image_path: str = ""
    text_label: str = "unknown"
    image_label: str = "unknown"
    disaster_label: str = "unknown"
    case_label: str = "unknown"
    review_status: str = "candidate"
    source: str = ""
    source_query: str = ""
    collected_at: str = ""
    notes: str = ""
    author_id: str = ""
    created_at: str = ""
    media_type: str = ""
    download_error: str = ""
    text_confidence: float = 0.0
    image_confidence: float = 0.0
    disaster_confidence: float = 0.0
    label_explanation: str = ""
    label_model: str = ""
    labeled_at: str = ""

    def __post_init__(self) -> None:
        if self.text_label not in TEXT_LABELS:
            raise ValueError(f"Invalid text_label: {self.text_label}")
        if self.image_label not in IMAGE_LABELS:
            raise ValueError(f"Invalid image_label: {self.image_label}")
        if self.disaster_label not in DISASTER_LABELS:
            raise ValueError(f"Invalid disaster_label: {self.disaster_label}")
        if self.review_status not in REVIEW_STATUSES:
            raise ValueError(f"Invalid review_status: {self.review_status}")
        if not self.collected_at:
            self.collected_at = datetime.now(UTC).isoformat()
