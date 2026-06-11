from pathlib import Path


def test_run_script_wraps_collection_workflow():
    script = Path("run_agent.sh")

    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "LIMIT=\"${1:-10}\"" in content
    assert "research-agent init" in content
    assert "research-agent collect --config \"$CONFIG_PATH\" --limit \"$LIMIT\"" in content
    assert "research-agent download-images" in content
    assert "research-agent balance" in content
    assert "research-agent export --output \"$EXPORT_PATH\"" in content
