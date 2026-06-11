from research_agent.balancer import balanced_target_met, high_confidence_case_counts
from research_agent.models import Candidate


def test_high_confidence_case_counts_excludes_low_confidence_rows():
    candidates = [
        Candidate(
            tweet_id="1",
            image_id="img1",
            text_label="literal",
            image_label="literal",
            disaster_label="real_disaster",
            case_label="literal_text__literal_image__real_disaster",
            text_confidence=0.9,
            image_confidence=0.9,
            disaster_confidence=0.9,
        ),
        Candidate(
            tweet_id="2",
            image_id="img2",
            text_label="literal",
            image_label="literal",
            disaster_label="real_disaster",
            case_label="literal_text__literal_image__real_disaster",
            text_confidence=0.4,
            image_confidence=0.9,
            disaster_confidence=0.9,
        ),
    ]

    counts = high_confidence_case_counts(candidates, min_confidence=0.65)

    assert counts["literal_text__literal_image__real_disaster"] == 1


def test_balanced_target_met_requires_all_cases_at_target():
    counts = {f"case_{index}": 2 for index in range(8)}
    assert balanced_target_met(counts, target_per_case=2)
    counts["case_7"] = 1
    assert not balanced_target_met(counts, target_per_case=2)
