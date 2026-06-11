from pathlib import Path


def test_market003b_script_is_dry_run_first_and_market_evidence_only() -> None:
    script = Path("scripts/run_market003b_manual_observation_backfill.py").read_text(encoding="utf-8")

    assert "Dry-run by default" in script
    assert "--write" in script
    assert "market_evidence" in script
    assert "creates candidates" in script
    assert "mutates gates" in script
    assert "changes scheduler" in script


def test_market003b_script_does_not_accept_csv_or_export_input() -> None:
    script = Path("scripts/run_market003b_manual_observation_backfill.py").read_text(encoding="utf-8")

    assert "--companies-file" not in script
    assert "csv" not in script.lower()
    assert "read_csv" not in script
