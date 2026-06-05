from __future__ import annotations

from pathlib import Path

SCRIPT = Path("scripts/run_employer_origin_reprocess_benchmark.py")


def test_reprocess_benchmark_has_duplicate_identity_preflight_guard() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "load_duplicate_candidate_identities" in text
    assert "candidate_identity_duplicates_detected" in text
    assert "duplicate_candidate_identity:" in text
    assert "ABORT: duplicate candidate identity detected" in text
    assert "dry_run warning: duplicate candidate identities exist" in text


def test_reprocess_benchmark_duplicate_identity_is_exact_and_non_constraint_based() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "selected.source_name_candidate IS NOT DISTINCT FROM c.source_name_candidate" in text
    assert "This is intentionally a preflight guard, not a DB constraint" in text
    assert "HAVING COUNT(*) > 1" in text


def test_duplicate_dry_run_suppresses_mutating_plan_message() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "duplicate_warning_blocks_mutating_dry_run = bool(duplicates) and not args.apply" in text
    assert "dry_run: reset plan suppressed because duplicate candidate identities exist" in text
    assert "dry_run next-safe plan suppressed: duplicate candidate identities must be reviewed before --apply" in text
