import zipfile

from research_agent.auto_label import AutoLabelResult, OpenAIClassifier
from research_agent.cli import main
from research_agent.models import Candidate
from research_agent.store import CandidateStore
from research_agent.x_api import XApiClient


def test_cli_init_creates_expected_files(tmp_path):
    exit_code = main(["--workspace", str(tmp_path), "init"])

    assert exit_code == 0
    assert (tmp_path / "data" / "research_agent.sqlite").exists()
    assert (tmp_path / "config" / "queries.yaml").exists()
    assert (tmp_path / "exports").is_dir()


def test_cli_import_balance_and_export(tmp_path, capsys):
    main(["--workspace", str(tmp_path), "init"])
    import_file = tmp_path / "tweets.txt"
    import_file.write_text("https://x.com/user/status/123\n", encoding="utf-8")

    import_exit = main(["--workspace", str(tmp_path), "import", str(import_file)])
    balance_exit = main(["--workspace", str(tmp_path), "balance"])
    export_exit = main(["--workspace", str(tmp_path), "export"])

    output = capsys.readouterr().out
    assert import_exit == 0
    assert balance_exit == 0
    assert export_exit == 0
    assert "Imported 1 candidate references" in output
    assert "literal_text__literal_image__real_disaster" in output
    assert "incomplete_or_unknown_labels: total=1" in output
    export_path = tmp_path / "exports" / "candidates.xlsx"
    with zipfile.ZipFile(export_path) as workbook:
        assert "xl/workbook.xml" in workbook.namelist()


def test_cli_import_missing_file_returns_clean_error(tmp_path, capsys):
    main(["--workspace", str(tmp_path), "init"])

    exit_code = main(["--workspace", str(tmp_path), "import", str(tmp_path / "missing.txt")])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "Import file not found" in output.err


def test_cli_collect_without_token_returns_failure(tmp_path, monkeypatch):
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    main(["--workspace", str(tmp_path), "init"])

    exit_code = main(["--workspace", str(tmp_path), "collect", "--limit", "10"])

    assert exit_code == 1


def test_cli_collect_reads_token_from_workspace_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    main(["--workspace", str(tmp_path), "init"])
    (tmp_path / ".env").write_text("X_BEARER_TOKEN=from-dotenv\n", encoding="utf-8")
    seen_tokens = []

    def fake_search_recent(self, query, max_results=100):
        seen_tokens.append(self.bearer_token)
        return {"data": [], "includes": {"media": []}}

    monkeypatch.setattr(XApiClient, "search_recent", fake_search_recent)

    exit_code = main(["--workspace", str(tmp_path), "collect", "--limit", "10"])

    assert exit_code == 0
    assert seen_tokens
    assert set(seen_tokens) == {"from-dotenv"}


def test_cli_collect_stops_after_credits_depleted(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("X_BEARER_TOKEN", "token")
    main(["--workspace", str(tmp_path), "init"])
    calls = []

    def fake_search_recent(self, query, max_results=100):
        calls.append(query)
        raise RuntimeError(
            'X API request failed with HTTP 402: {"title":"CreditsDepleted"}'
        )

    monkeypatch.setattr(XApiClient, "search_recent", fake_search_recent)

    exit_code = main(["--workspace", str(tmp_path), "collect", "--limit", "10"])

    output = capsys.readouterr()
    assert exit_code == 1
    assert len(calls) == 1
    assert "X API credits are depleted" in output.err


def test_cli_collect_filters_non_disaster_candidates_without_required_terms(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("X_BEARER_TOKEN", "token")
    main(["--workspace", str(tmp_path), "init"])
    config_path = tmp_path / "config" / "non_disaster_required_terms.yaml"
    config_path.write_text(
        """queries:
  - name: non_disaster_test
    query: '("storm" OR "poster") has:images lang:en -is:retweet'
    required_terms:
      - storm
      - flood
    seed_labels:
      disaster_label: not_real_disaster
""",
        encoding="utf-8",
    )

    def fake_search_recent(self, query, max_results=100):
        return {
            "data": [
                {
                    "id": "1",
                    "text": "Big announcement with a new poster.",
                    "attachments": {"media_keys": ["3_skip"]},
                },
                {
                    "id": "2",
                    "text": "A political storm is building around the policy.",
                    "attachments": {"media_keys": ["3_keep"]},
                },
            ],
            "includes": {
                "media": [
                    {
                        "media_key": "3_skip",
                        "type": "photo",
                        "url": "https://example.com/skip.jpg",
                    },
                    {
                        "media_key": "3_keep",
                        "type": "photo",
                        "url": "https://example.com/keep.jpg",
                    },
                ]
            },
        }

    monkeypatch.setattr(XApiClient, "search_recent", fake_search_recent)

    exit_code = main(
        [
            "--workspace",
            str(tmp_path),
            "collect",
            "--config",
            str(config_path),
            "--limit",
            "10",
        ]
    )

    assert exit_code == 0
    rows = _candidate_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["tweet_id"] == "2"


def test_cli_auto_label_requires_openai_key(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    main(["--workspace", str(tmp_path), "init"])

    exit_code = main(["--workspace", str(tmp_path), "auto-label"])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "OPENAI_API_KEY is required" in output.err


def test_cli_auto_label_updates_candidate_with_fake_classifier(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    main(["--workspace", str(tmp_path), "init"])
    store = CandidateStore(tmp_path / "data" / "research_agent.sqlite")
    store.upsert_candidate(
        Candidate(
            tweet_id="123",
            image_id="img",
            image_url="https://example.com/img.jpg",
        )
    )

    def fake_classify(self, candidate):
        return AutoLabelResult(
            text_label="figurative",
            image_label="literal",
            disaster_label="not_real_disaster",
            text_confidence=0.91,
            image_confidence=0.82,
            disaster_confidence=0.88,
            explanation="Fake classification.",
        )

    monkeypatch.setattr(OpenAIClassifier, "classify", fake_classify)

    exit_code = main(["--workspace", str(tmp_path), "auto-label", "--limit", "1"])

    assert exit_code == 0
    rows = _candidate_rows(tmp_path)
    assert rows[0]["text_label"] == "figurative"
    assert rows[0]["image_label"] == "literal"
    assert rows[0]["disaster_label"] == "not_real_disaster"
    assert rows[0]["case_label"] == "figurative_text__literal_image__not_real_disaster"


def test_cli_auto_label_skips_candidates_without_images(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    main(["--workspace", str(tmp_path), "init"])
    import_file = tmp_path / "tweets.txt"
    import_file.write_text("https://x.com/user/status/123\n", encoding="utf-8")
    main(["--workspace", str(tmp_path), "import", str(import_file)])

    exit_code = main(["--workspace", str(tmp_path), "auto-label", "--limit", "1"])

    output = capsys.readouterr()
    assert exit_code == 0
    assert "Skipped 1 candidates without images" in output.out
    assert "Auto-label failed" not in output.err


def test_cli_collect_balanced_runs_round_and_exports(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    main(["--workspace", str(tmp_path), "init"])

    def fake_collect(store, workspace, config_path, limit):
        store.upsert_candidate(
            Candidate(
                tweet_id="1",
                image_id="img",
                tweet_text="Flooding downtown.",
                image_url="https://example.com/img.jpg",
            )
        )
        return 1, 0

    def fake_classify(self, candidate):
        return AutoLabelResult(
            text_label="literal",
            image_label="literal",
            disaster_label="real_disaster",
            text_confidence=0.95,
            image_confidence=0.95,
            disaster_confidence=0.95,
            explanation="Direct report.",
        )

    monkeypatch.setattr("research_agent.cli._collect_from_config", fake_collect)
    monkeypatch.setattr(OpenAIClassifier, "classify", fake_classify)

    exit_code = main(
        [
            "--workspace",
            str(tmp_path),
            "collect-balanced",
            "--target-per-case",
            "1",
            "--max-rounds",
            "1",
            "--limit-per-query",
            "10",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "exports" / "candidates.xlsx").exists()


def _candidate_rows(workspace):
    import sqlite3

    connection = sqlite3.connect(workspace / "data" / "research_agent.sqlite")
    connection.row_factory = sqlite3.Row
    return connection.execute("select * from candidates order by tweet_id").fetchall()
