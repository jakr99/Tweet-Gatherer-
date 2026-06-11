import sqlite3

from research_agent.importer import parse_tweet_reference, read_import_file
from research_agent.models import Candidate
from research_agent.store import CandidateStore


def test_parse_tweet_reference_accepts_urls_and_raw_ids():
    assert parse_tweet_reference("https://x.com/user/status/1234567890") == "1234567890"
    assert parse_tweet_reference("https://twitter.com/user/status/98765?s=20") == "98765"
    assert parse_tweet_reference(" 55555 ") == "55555"


def test_read_import_file_supports_plain_text_and_csv(tmp_path):
    text_file = tmp_path / "ids.txt"
    text_file.write_text("https://x.com/a/status/111\n222\n", encoding="utf-8")
    csv_file = tmp_path / "ids.csv"
    csv_file.write_text("tweet_url,notes\nhttps://x.com/b/status/333,example\n", encoding="utf-8")

    assert read_import_file(text_file) == ["111", "222"]
    assert read_import_file(csv_file) == ["333"]


def test_store_upserts_candidates_without_duplicates(tmp_path):
    store = CandidateStore(tmp_path / "agent.sqlite")
    store.initialize()
    candidate = Candidate(
        tweet_id="1",
        image_id="media1",
        tweet_text="Flood waters rising",
        image_url="https://example.com/media1.jpg",
        disaster_label="real_disaster",
        source="test",
        source_query="flood has:images",
    )

    store.upsert_candidate(candidate)
    store.upsert_candidate(candidate)

    rows = store.list_candidates()
    assert len(rows) == 1
    assert rows[0].case_label == "unknown"

    with sqlite3.connect(tmp_path / "agent.sqlite") as connection:
        count = connection.execute("select count(*) from candidates").fetchone()[0]
    assert count == 1
