from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_f6_initial_assessment_materialization import (
    APPROVAL_TOKEN,
    F6InitialAssessmentStop,
    REPORT_SCHEMA,
    verify_frozen_fingerprint,
)


SCRIPT = Path("scripts/run_f6_initial_assessment_materialization.py")


def _plan(fingerprint: str) -> dict[str, object]:
    return {
        "proposals": [
            {
                "silver_job_id": 626,
                "materialization_fingerprint": fingerprint,
            }
        ]
    }


def test_exact_frozen_fingerprint_is_required() -> None:
    fingerprint = "7" * 64
    verify_frozen_fingerprint(
        _plan(fingerprint),
        silver_job_id=626,
        expected_fingerprint=fingerprint,
    )

    with pytest.raises(F6InitialAssessmentStop, match="fingerprint mismatch"):
        verify_frozen_fingerprint(
            _plan("8" * 64),
            silver_job_id=626,
            expected_fingerprint=fingerprint,
        )


def test_f6_apply_gate_is_single_insert_only_and_postwrite_proven() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert APPROVAL_TOKEN == "F6-INITIAL-ASSESSMENT-MATERIALIZE"
    assert REPORT_SCHEMA == "job_application_pipeline.f6_initial_assessment_materialization.v1"
    assert '"assessment_insert_max": 1' in source
    assert '"assessment_updates": False' in source
    assert '"capability_fit_created": False' in source
    assert '"ranking_scores_created": False' in source
    assert '"top5_forced": False' in source
    assert '"application_or_submission_writes": False' in source
    assert 'payload.get("product_readiness_status") == "hard_filter_evidence_required"' in source
    assert "postwrite_proof(" in source
