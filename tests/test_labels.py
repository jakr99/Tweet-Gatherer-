from research_agent.labels import ALL_CASES, balance_rows, derive_case_label
from research_agent.models import Candidate


def test_derive_case_label_for_requested_disaster_cell():
    assert (
        derive_case_label("figurative", "literal", "real_disaster")
        == "figurative_text__literal_image__real_disaster"
    )


def test_derive_case_label_returns_unknown_when_any_dimension_unknown():
    assert derive_case_label("literal", "unknown", "real_disaster") == "unknown"


def test_balance_rows_include_all_cases_with_zero_counts():
    candidate = Candidate(
        tweet_id="1",
        image_id="img1",
        tweet_text="The city is drowning after the flood.",
        image_url="https://example.com/img.jpg",
        text_label="figurative",
        image_label="literal",
        disaster_label="real_disaster",
        review_status="candidate",
    )

    rows = balance_rows([candidate])

    assert [row["case_label"] for row in rows] == ALL_CASES
    target = {
        row["case_label"]: row
        for row in rows
    }["figurative_text__literal_image__real_disaster"]
    assert target["candidate"] == 1
    assert target["accepted"] == 0
    zero_row = {
        row["case_label"]: row
        for row in rows
    }["literal_text__literal_image__not_real_disaster"]
    assert zero_row["total"] == 0
