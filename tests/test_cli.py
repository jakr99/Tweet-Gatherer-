import zipfile

from research_agent.cli import main


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
    export_path = tmp_path / "exports" / "candidates.xlsx"
    with zipfile.ZipFile(export_path) as workbook:
        assert "xl/workbook.xml" in workbook.namelist()


def test_cli_collect_without_token_returns_failure(tmp_path, monkeypatch):
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    main(["--workspace", str(tmp_path), "init"])

    exit_code = main(["--workspace", str(tmp_path), "collect", "--limit", "10"])

    assert exit_code == 1
