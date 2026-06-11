import zipfile

from research_agent.exporter import export_workbook
from research_agent.images import image_path_for_candidate, record_image_downloads
from research_agent.models import Candidate
from research_agent.store import CandidateStore


def test_image_path_for_candidate_uses_tweet_and_image_ids(tmp_path):
    candidate = Candidate(
        tweet_id="123",
        image_id="3_abc",
        image_url="https://pbs.twimg.com/media/abc.jpg?format=jpg&name=large",
    )

    path = image_path_for_candidate(candidate, tmp_path)

    assert path == tmp_path / "123" / "3_abc.jpg"


def test_record_image_downloads_preserves_failed_rows(tmp_path):
    store = CandidateStore(tmp_path / "agent.sqlite")
    store.upsert_candidate(
        Candidate(
            tweet_id="1",
            image_id="img",
            image_url="https://example.invalid/missing.jpg",
        )
    )

    record_image_downloads(store, tmp_path / "images", downloader=lambda url: None)

    row = store.list_candidates()[0]
    assert row.image_path == ""
    assert "No bytes returned" in row.download_error


def test_export_workbook_contains_required_sheets(tmp_path):
    store = CandidateStore(tmp_path / "agent.sqlite")
    store.upsert_candidate(
        Candidate(
            tweet_id="1",
            image_id="img",
            tweet_text="Flood waters rising",
            image_url="https://example.com/img.jpg",
            text_label="literal",
            image_label="literal",
            disaster_label="real_disaster",
            source_query="flood_real",
        )
    )
    output_path = tmp_path / "exports" / "candidates.xlsx"

    export_workbook(store, output_path)

    with zipfile.ZipFile(output_path) as workbook:
        workbook_xml = workbook.read("xl/workbook.xml").decode("utf-8")
    assert 'name="candidates"' in workbook_xml
    assert 'name="balance_summary"' in workbook_xml
    assert 'name="collection_runs"' in workbook_xml


def test_export_empty_store_still_writes_candidate_headers(tmp_path):
    store = CandidateStore(tmp_path / "agent.sqlite")
    store.initialize()
    output_path = tmp_path / "exports" / "empty.xlsx"

    export_workbook(store, output_path)

    with zipfile.ZipFile(output_path) as workbook:
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "tweet_id" in sheet_xml
    assert "image_id" in sheet_xml
    assert "image_url" in sheet_xml
