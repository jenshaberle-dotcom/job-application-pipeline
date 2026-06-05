from pathlib import Path


def test_eo002_script_keeps_mutating_boundary_explicit() -> None:
    script = Path("scripts/run_market_sensor_candidate_promotion_batch.py").read_text(encoding="utf-8")

    assert "dry-run first" in script
    assert "no browsing" in script
    assert "no gate mutation" in script
    assert "no connector build" in script
    assert "no Bronze/Silver write" in script
    assert "no scheduler change" in script
    assert "--apply" in script


def test_eo002_script_requires_manual_review_opt_in() -> None:
    script = Path("scripts/run_market_sensor_candidate_promotion_batch.py").read_text(encoding="utf-8")

    assert "--include-manual-review-required" in script
    assert "Duplicate --company-key values are not allowed" in script
    assert "Candidate URL intentionally left NULL for Origin Source Discovery" in script
