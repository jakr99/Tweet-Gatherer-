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
