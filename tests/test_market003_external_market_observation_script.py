from pathlib import Path


def test_market003_script_is_dry_run_first_and_boundary_explicit() -> None:
    script = Path("scripts/run_market003_external_market_observation.py").read_text(encoding="utf-8")

    assert "Dry-run by default" in script
    assert "market_evidence only" in script
    assert "--write" in script
    assert "--review-only" in script
    assert "no job ingestion" in script
    assert "no Bronze/Silver/Gold write" in script
    assert "no candidate creation" in script
    assert "no gate decision" in script
    assert "no connector activation" in script
    assert "no scheduler change" in script


def test_legacy_market_evidence_script_uses_market003_manual_kind() -> None:
    script = Path("scripts/record_market_evidence.py").read_text(encoding="utf-8")

    assert "manual_market_observation" in script
    assert "observation_origin" in script
    assert 'default="manual_market_observation"' in script
    assert "manual_aggregator_sighting" not in script
