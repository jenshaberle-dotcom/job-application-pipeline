from pathlib import Path

SCRIPT = Path("scripts/run_employer_origin_source_url_recovery_agent.py").read_text(encoding="utf-8")


def test_url_recovery_is_dry_run_first() -> None:
    assert '"--apply"' in SCRIPT
    assert "Persist candidate_url/gate-state changes. Default is dry-run." in SCRIPT
    assert "if args.apply:" in SCRIPT
    assert "source_url_recovery_result: recovered_dry_run" in SCRIPT
    assert "source_url_recovery_result: manual_review_required_dry_run" in SCRIPT


def test_followup_gate_review_requires_apply() -> None:
    assert "if args.run_gate_review_after_recovery and not args.apply:" in SCRIPT
    assert "error: --run-gate-review-after-recovery requires --apply" in SCRIPT


def test_null_candidate_url_is_not_loaded_as_literal_none() -> None:
    assert 'candidate_url=str(row["candidate_url"] or "")' in SCRIPT
