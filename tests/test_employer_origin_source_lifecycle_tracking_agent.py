from __future__ import annotations

from scripts.run_employer_origin_source_lifecycle_tracking_agent import (
    LifecycleMetrics,
    SourceCandidate,
    build_lifecycle_outcome,
    lifecycle_report_lines,
)


def make_candidate(status: str = "active_controlled") -> SourceCandidate:
    return SourceCandidate(
        id=1,
        company_key="finanz_informatik",
        company_name="Finanz Informatik GmbH & Co. KG",
        source_name_candidate="finanz_informatik:hannover",
        status=status,
        risk_level="low",
    )


def make_metrics(raw: int, silver: int, runs: int = 1) -> LifecycleMetrics:
    return LifecycleMetrics(
        source_name="finanz_informatik:hannover",
        raw_job_count=raw,
        silver_job_count=silver,
        ingestion_run_count=runs,
        latest_raw_fetched_at="2026-05-29 12:00:00+00",
        latest_ingestion_run_id=372,
    )


def test_lifecycle_outcome_passes_when_source_has_raw_and_silver_evidence() -> None:
    outcome = build_lifecycle_outcome(make_candidate(), make_metrics(raw=3, silver=3))

    assert outcome.gate_status == "passed"
    assert outcome.decision == "continue"
    assert outcome.stop_reason is None
    assert outcome.evidence["raw_job_count"] == 3
    assert outcome.evidence["silver_job_count"] == 3
    assert outcome.evidence["boundary"]["csv_or_export_inputs_used"] is False


def test_lifecycle_outcome_requires_review_when_raw_has_no_silver_value() -> None:
    outcome = build_lifecycle_outcome(make_candidate(), make_metrics(raw=3, silver=0))

    assert outcome.gate_status == "manual_review_required"
    assert outcome.decision == "manual_review_required"
    assert outcome.stop_reason == "source has raw evidence but no Silver evidence"


def test_lifecycle_outcome_requires_review_when_source_has_no_raw_evidence() -> None:
    outcome = build_lifecycle_outcome(make_candidate(), make_metrics(raw=0, silver=0, runs=0))

    assert outcome.gate_status == "manual_review_required"
    assert outcome.decision == "manual_review_required"
    assert outcome.stop_reason == "source has no raw evidence"


def test_lifecycle_report_lines_are_actionable() -> None:
    outcome = build_lifecycle_outcome(make_candidate(), make_metrics(raw=3, silver=3))
    text = "\n".join(lifecycle_report_lines(make_candidate(), outcome))

    assert "source_lifecycle_tracking: passed / continue" in text
    assert "raw_job_count: 3" in text
    assert "silver_job_count: 3" in text
    assert "NEXT: lifecycle gate is now tracked from DB evidence." in text
