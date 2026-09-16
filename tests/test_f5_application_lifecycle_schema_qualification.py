from __future__ import annotations

import pytest

from scripts.run_f5_application_lifecycle_schema_qualification import (
    QualificationStop,
    TARGET_MIGRATION,
    TARGET_TABLES,
    TARGET_VIEW,
    validate_report,
)


SOURCE_SHA = "b" * 40


def _report(*, phase: str = "preflight") -> dict[str, object]:
    return {
        "phase": phase,
        "source_sha": SOURCE_SHA,
        "boundaries": {
            "db_writes": 0,
            "provider_calls": 0,
            "gmail_reads": 0,
            "email_actions": 0,
            "application_submission_actions": 0,
            "application_state_mutations": 0,
        },
    }


def test_slice_b_targets_exact_migration_and_relations() -> None:
    assert TARGET_MIGRATION == "112_create_authoritative_application_lifecycle.sql"
    assert TARGET_TABLES == (
        "applications",
        "application_submissions",
        "application_lifecycle_events",
        "application_event_candidates",
    )
    assert TARGET_VIEW == "gold_product_v1_application_tracking"


def test_validation_accepts_zero_effect_read_only_proof() -> None:
    validate_report(_report(), phase="preflight", source_sha=SOURCE_SHA)


def test_validation_rejects_source_drift() -> None:
    with pytest.raises(QualificationStop, match="SOURCE_SHA_MISMATCH"):
        validate_report(_report(), phase="preflight", source_sha="c" * 40)


def test_validation_rejects_phase_drift() -> None:
    with pytest.raises(QualificationStop, match="PHASE_MISMATCH"):
        validate_report(_report(phase="postapply"), phase="preflight", source_sha=SOURCE_SHA)


def test_validation_fails_closed_on_any_effect_boundary() -> None:
    for boundary in (
        "db_writes",
        "provider_calls",
        "gmail_reads",
        "email_actions",
        "application_submission_actions",
        "application_state_mutations",
    ):
        report = _report()
        report["boundaries"] = dict(report["boundaries"])
        report["boundaries"][boundary] = 1
        with pytest.raises(QualificationStop, match=f"BOUNDARY_NOT_ZERO:{boundary}"):
            validate_report(report, phase="preflight", source_sha=SOURCE_SHA)
