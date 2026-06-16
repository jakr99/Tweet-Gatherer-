import sqlite3

from research_agent.models import Candidate
from research_agent.store import CandidateStore


def test_store_migrates_label_metadata_columns(tmp_path):
    store = CandidateStore(tmp_path / "agent.sqlite")
    store.initialize()

    with sqlite3.connect(tmp_path / "agent.sqlite") as connection:
        columns = {
            row[1]
            for row in connection.execute("pragma table_info(candidates)").fetchall()
        }

    assert "text_confidence" in columns
    assert "image_confidence" in columns
    assert "disaster_confidence" in columns
    assert "label_explanation" in columns
    assert "label_model" in columns
    assert "labeled_at" in columns


def test_store_updates_candidate_labels_and_metadata(tmp_path):
    store = CandidateStore(tmp_path / "agent.sqlite")
    store.upsert_candidate(Candidate(tweet_id="1", image_id="img1"))

    store.update_candidate_labels(
        tweet_id="1",
        image_id="img1",
        text_label="figurative",
        image_label="literal",
        disaster_label="real_disaster",
        text_confidence=0.91,
        image_confidence=0.82,
        disaster_confidence=0.95,
        label_explanation="Metaphorical text with direct disaster image.",
        label_model="gpt-test",
        labeled_at="2026-06-11T00:00:00+00:00",
    )

    row = store.list_candidates()[0]
    assert row.text_label == "figurative"
    assert row.image_label == "literal"
    assert row.disaster_label == "real_disaster"
    assert row.case_label == "figurative_text__literal_image__real_disaster"
    assert row.text_confidence == 0.91
    assert row.label_explanation == "Metaphorical text with direct disaster image."
    assert row.label_model == "gpt-test"
    assert row.labeled_at == "2026-06-11T00:00:00+00:00"


def test_store_lists_candidates_needing_labels(tmp_path):
    store = CandidateStore(tmp_path / "agent.sqlite")
    store.upsert_candidate(Candidate(tweet_id="1", image_id="unknown"))
    store.upsert_candidate(
        Candidate(
            tweet_id="2",
            image_id="labeled",
            text_label="literal",
            image_label="literal",
            disaster_label="real_disaster",
        )
    )

    rows = store.list_candidates_needing_labels(limit=10)

    assert [(row.tweet_id, row.image_id) for row in rows] == [("1", "unknown")]


def test_store_upsert_preserves_existing_labels_when_collection_sees_duplicate(tmp_path):
    store = CandidateStore(tmp_path / "agent.sqlite")
    store.upsert_candidate(
        Candidate(
            tweet_id="1",
            image_id="img1",
            tweet_text="Original labeled text",
            image_url="https://example.com/original.jpg",
            text_label="figurative",
            image_label="literal",
            disaster_label="real_disaster",
            text_confidence=0.91,
            image_confidence=0.82,
            disaster_confidence=0.95,
            label_explanation="Already labeled.",
            label_model="gpt-test",
            labeled_at="2026-06-15T00:00:00+00:00",
        )
    )

    store.upsert_candidate(
        Candidate(
            tweet_id="1",
            image_id="img1",
            tweet_text="Duplicate collected text",
            image_url="https://example.com/new.jpg",
            disaster_label="real_disaster",
            source_query="duplicate_query",
        )
    )

    row = store.list_candidates()[0]
    assert row.tweet_text == "Duplicate collected text"
    assert row.image_url == "https://example.com/new.jpg"
    assert row.text_label == "figurative"
    assert row.image_label == "literal"
    assert row.disaster_label == "real_disaster"
    assert row.case_label == "figurative_text__literal_image__real_disaster"
    assert row.text_confidence == 0.91
    assert row.label_explanation == "Already labeled."
    assert row.label_model == "gpt-test"
    assert row.labeled_at == "2026-06-15T00:00:00+00:00"
