import zipfile

from research_agent.auto_label import AutoLabelResult, OpenAIClassifier
from research_agent.cli import main
from research_agent.labels import ALL_CASES
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


def test_cli_auto_label_updates_candidate_with_fake_classifier(tmp_path, monkeypatch, capsys):
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

    output = capsys.readouterr()
    assert exit_code == 0
    assert "Auto-labeling 1 candidates" in output.out
    assert "Labeling 1/1: 123/img" in output.out
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


def test_cli_fill_balanced_prunes_overflow_and_reaches_target(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    main(["--workspace", str(tmp_path), "init"])

    def fake_collect(
        store,
        workspace,
        config_path,
        limit,
        pagination_tokens=None,
        active_case_labels=None,
    ):
        for index, case_label in enumerate(ALL_CASES):
            text_label, image_label, disaster_label = _labels_from_case(case_label)
            store.upsert_candidate(
                Candidate(
                    tweet_id=f"{index}",
                    image_id="img",
                    tweet_text=_tweet_text_for_case(case_label, index),
                    image_url=f"https://example.com/{index}.jpg",
                    text_label=text_label,
                    image_label=image_label,
                    disaster_label=disaster_label,
                    text_confidence=0.95,
                    image_confidence=0.95,
                    disaster_confidence=0.95,
                )
            )
        store.upsert_candidate(
            Candidate(
                tweet_id="overflow",
                image_id="img",
                tweet_text="Overflow candidate",
                image_url="https://example.com/overflow.jpg",
                text_label="literal",
                image_label="literal",
                disaster_label="real_disaster",
                text_confidence=0.70,
                image_confidence=0.70,
                disaster_confidence=0.70,
            )
        )
        return len(ALL_CASES) + 1, 0

    def fake_auto_label(store, limit, relabel=False):
        return 0, 0

    monkeypatch.setattr("research_agent.cli._collect_from_config", fake_collect)
    monkeypatch.setattr("research_agent.cli._auto_label_candidates", fake_auto_label)

    exit_code = main(
        [
            "--workspace",
            str(tmp_path),
            "fill-balanced",
            "--target-per-case",
            "1",
            "--max-rounds",
            "1",
            "--limit-per-query",
            "10",
        ]
    )

    assert exit_code == 0
    rows = _candidate_rows(tmp_path)
    assert len(rows) == len(ALL_CASES)
    assert {row["case_label"] for row in rows} == set(ALL_CASES)
    assert (tmp_path / "exports" / "candidates.xlsx").exists()


def test_cli_fill_balanced_only_runs_queries_for_underfilled_cases(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    main(["--workspace", str(tmp_path), "init"])
    config_path = tmp_path / "config" / "targeted_queries.yaml"
    full_case = "literal_text__literal_image__real_disaster"
    low_case = "figurative_text__literal_image__not_real_disaster"
    config_path.write_text(
        f"""queries:
  - name: full_bucket_query
    query: 'full bucket query has:images'
    target_cases:
      - {full_case}
    seed_labels:
      disaster_label: real_disaster
  - name: low_bucket_query
    query: 'low bucket query has:images'
    target_cases:
      - {low_case}
    seed_labels:
      disaster_label: not_real_disaster
""",
        encoding="utf-8",
    )
    store = CandidateStore(tmp_path / "data" / "research_agent.sqlite")
    store.upsert_candidate(
        Candidate(
            tweet_id="full",
            image_id="img",
            tweet_text="Full bucket candidate",
            image_url="https://example.com/full.jpg",
            text_label="literal",
            image_label="literal",
            disaster_label="real_disaster",
            text_confidence=0.95,
            image_confidence=0.95,
            disaster_confidence=0.95,
        )
    )
    seen_queries = []

    def fake_search_recent(self, query, max_results=100, next_token=None):
        seen_queries.append(query)
        return {"data": [], "includes": {"media": []}}

    def fake_auto_label(store, limit, relabel=False):
        return 0, 0

    monkeypatch.setattr(XApiClient, "search_recent", fake_search_recent)
    monkeypatch.setattr("research_agent.cli._auto_label_candidates", fake_auto_label)

    exit_code = main(
        [
            "--workspace",
            str(tmp_path),
            "fill-balanced",
            "--config",
            str(config_path),
            "--target-per-case",
            "1",
            "--max-rounds",
            "1",
            "--limit-per-query",
            "10",
        ]
    )

    assert exit_code == 1
    assert seen_queries == ["low bucket query has:images"]


def test_cli_fill_balanced_labels_all_unlabeled_candidates(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    main(["--workspace", str(tmp_path), "init"])
    seen_limits = []

    def fake_collect(
        store,
        workspace,
        config_path,
        limit,
        pagination_tokens=None,
        active_case_labels=None,
    ):
        for index in range(3):
            store.upsert_candidate(
                Candidate(
                    tweet_id=f"unknown-{index}",
                    image_id="img",
                    image_url=f"https://example.com/{index}.jpg",
                )
            )
        return 3, 0

    def fake_auto_label(store, limit, relabel=False):
        seen_limits.append(limit)
        return 0, 0

    monkeypatch.setattr("research_agent.cli._collect_from_config", fake_collect)
    monkeypatch.setattr("research_agent.cli._auto_label_candidates", fake_auto_label)

    main(
        [
            "--workspace",
            str(tmp_path),
            "fill-balanced",
            "--target-per-case",
            "1",
            "--max-rounds",
            "1",
            "--limit-per-query",
            "10",
        ]
    )

    assert seen_limits == [3]


def test_cli_fill_balanced_removes_unlabeled_leftovers_before_export(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    main(["--workspace", str(tmp_path), "init"])

    def fake_collect(
        store,
        workspace,
        config_path,
        limit,
        pagination_tokens=None,
        active_case_labels=None,
    ):
        store.upsert_candidate(
            Candidate(
                tweet_id="unknown",
                image_id="img",
                image_url="https://example.com/unknown.jpg",
            )
        )
        return 1, 0

    def fake_auto_label(store, limit, relabel=False):
        return 0, 0

    monkeypatch.setattr("research_agent.cli._collect_from_config", fake_collect)
    monkeypatch.setattr("research_agent.cli._auto_label_candidates", fake_auto_label)

    exit_code = main(
        [
            "--workspace",
            str(tmp_path),
            "fill-balanced",
            "--target-per-case",
            "1",
            "--max-rounds",
            "1",
            "--limit-per-query",
            "10",
        ]
    )

    assert exit_code == 1
    assert _candidate_rows(tmp_path) == []


def test_cli_fill_balanced_does_not_prune_low_confidence_rows_below_target(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    main(["--workspace", str(tmp_path), "init"])

    def fake_collect(
        store,
        workspace,
        config_path,
        limit,
        pagination_tokens=None,
        active_case_labels=None,
    ):
        store.upsert_candidate(
            Candidate(
                tweet_id="low-confidence",
                image_id="img",
                image_url="https://example.com/low.jpg",
                text_label="figurative",
                image_label="literal",
                disaster_label="real_disaster",
                text_confidence=0.99,
                image_confidence=0.40,
                disaster_confidence=0.99,
            )
        )
        return 1, 0

    def fake_auto_label(store, limit, relabel=False):
        return 0, 0

    monkeypatch.setattr("research_agent.cli._collect_from_config", fake_collect)
    monkeypatch.setattr("research_agent.cli._auto_label_candidates", fake_auto_label)

    main(
        [
            "--workspace",
            str(tmp_path),
            "fill-balanced",
            "--target-per-case",
            "1",
            "--max-rounds",
            "1",
            "--limit-per-query",
            "10",
        ]
    )

    rows = _candidate_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["tweet_id"] == "low-confidence"


def test_cli_fill_balanced_removes_non_disaster_rows_without_disaster_terms(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    main(["--workspace", str(tmp_path), "init"])

    def fake_collect(
        store,
        workspace,
        config_path,
        limit,
        pagination_tokens=None,
        active_case_labels=None,
    ):
        store.upsert_candidate(
            Candidate(
                tweet_id="sports",
                image_id="img",
                tweet_text="World Cup match update with goals and highlights.",
                image_url="https://example.com/sports.jpg",
                text_label="literal",
                image_label="literal",
                disaster_label="not_real_disaster",
                text_confidence=0.95,
                image_confidence=0.95,
                disaster_confidence=0.95,
            )
        )
        store.upsert_candidate(
            Candidate(
                tweet_id="metaphor",
                image_id="img",
                tweet_text="The team is on fire after a storm of criticism.",
                image_url="https://example.com/metaphor.jpg",
                text_label="figurative",
                image_label="literal",
                disaster_label="not_real_disaster",
                text_confidence=0.95,
                image_confidence=0.95,
                disaster_confidence=0.95,
            )
        )
        return 2, 0

    def fake_auto_label(store, limit, relabel=False):
        return 0, 0

    monkeypatch.setattr("research_agent.cli._collect_from_config", fake_collect)
    monkeypatch.setattr("research_agent.cli._auto_label_candidates", fake_auto_label)

    main(
        [
            "--workspace",
            str(tmp_path),
            "fill-balanced",
            "--target-per-case",
            "2",
            "--max-rounds",
            "1",
            "--limit-per-query",
            "10",
        ]
    )

    rows = _candidate_rows(tmp_path)
    assert [row["tweet_id"] for row in rows] == ["metaphor"]


def _candidate_rows(workspace):
    import sqlite3

    connection = sqlite3.connect(workspace / "data" / "research_agent.sqlite")
    connection.row_factory = sqlite3.Row
    return connection.execute("select * from candidates order by tweet_id").fetchall()


def _labels_from_case(case_label):
    text_part, rest = case_label.split("_text__", 1)
    image_part, disaster_label = rest.split("_image__", 1)
    return text_part, image_part, disaster_label


def _tweet_text_for_case(case_label, index):
    if case_label.endswith("not_real_disaster"):
        return f"Candidate {index} uses storm language outside a real disaster."
    return f"Candidate {index}"
