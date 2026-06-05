from pathlib import Path


def test_eo001_script_is_schema_safe_for_candidate_expansion_review_items() -> None:
    script = Path("scripts/run_market_sensor_origin_candidate_funnel_audit.py").read_text(encoding="utf-8")

    assert "review_status" not in script
    assert "decision" in script
    assert "candidate_expansion_review_items" in script
    assert "information_schema.columns" in script


def test_eo001_script_is_read_only_boundary() -> None:
    script = Path("scripts/run_market_sensor_origin_candidate_funnel_audit.py").read_text(encoding="utf-8")

    assert "no candidate creation" in script
    assert "no gate mutation" in script
    assert "no connector build" in script
    assert "no Bronze/Silver write" in script
