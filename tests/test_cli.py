import zipfile

from research_agent.cli import main
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
