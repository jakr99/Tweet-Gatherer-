from pathlib import Path


def test_run_script_wraps_collection_workflow():
    script = Path("run_agent.sh")

    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "LIMIT=\"${1:-10}\"" in content
    assert "research-agent init" in content
    assert "TARGET_PER_CASE=\"${TARGET_PER_CASE:-12}\"" in content
    assert "research-agent collect-balanced" in content
    assert "--limit-per-query \"$LIMIT\"" in content
    assert "--target-per-case \"$TARGET_PER_CASE\"" in content
    assert "--min-confidence \"$MIN_CONFIDENCE\"" in content
    assert "research-agent balance" in content


def test_collect_tweets_script_only_collects_downloads_and_exports():
    script = Path("collect_tweets.sh")

    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "research-agent collect --config \"$CONFIG_PATH\" --limit \"$LIMIT\"" in content
    assert "research-agent download-images" in content
    assert "research-agent export --output \"$EXPORT_PATH\"" in content
    assert "auto-label" not in content
    assert "collect-balanced" not in content


def test_label_tweets_script_only_labels_existing_candidates():
    script = Path("label_tweets.sh")

    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "research-agent auto-label --limit \"$LIMIT\" --min-confidence \"$MIN_CONFIDENCE\"" in content
    assert "research-agent balance" in content
    assert "research-agent export --output \"$EXPORT_PATH\"" in content
    assert "research-agent collect" not in content
    assert "download-images" not in content
