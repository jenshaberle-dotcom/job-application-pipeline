from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.run_product_v1_hard_filter_review import (
    HardFilterReviewStop,
    ReviewRequest,
    build_plan,
    parse_input,
)


MIGRATION = Path("db/migrations/102_create_product_v1_hard_filter_operator_reviews.sql")


def _row(
    *,
    deterministic: str = "unknown",
    capability_fit: str = "passed",
    employment: str = "manual_review_required",
    languages: str = "passed",
    weekly_hours: str = "manual_review_required",
    seniority: str = "passed",
) -> dict[str, object]:
    stamp = datetime(2026, 9, 2, 14, 0, tzinfo=UTC)
    return {
        "silver_job_id": 511,
        "title": "Data Engineer",
        "company_name": "Example GmbH",
        "source_name": "personio:example",
        "capability_fit_status": capability_fit,
        "assessment_updated_at": stamp,
        "employment_status": employment,
        "language_status": languages,
        "weekly_hours_status": weekly_hours,
        "seniority_status": seniority,
        "salary_signal": "unknown",
        "deterministic_hard_filter_status": deterministic,
        "hard_filter_status": deterministic,
        "hard_filter_reasons": {},
        "policy_version": "product-v1-2026-08-02",
        "operator_review_decision": None,
        "operator_review_valid": False,
        "active_review_decision": None,
        "active_review_rationale": None,
        "active_review_assessment_updated_at": None,
        "active_review_policy_version": None,
    }


def test_parse_input_requires_explicit_decision_and_reason() -> None:
    reviews = parse_input(
        {
            "schema": "job_application_pipeline.product_v1_hard_filter_review_input.v1",
            "reviews": [
                {
                    "silver_job_id": 511,
                    "decision": "passed",
                    "rationale": "Full-time source evidence reviewed; exact hours are not stated.",
                }
            ],
        }
    )
    assert reviews == (
        ReviewRequest(
            silver_job_id=511,
            decision="passed",
            rationale="Full-time source evidence reviewed; exact hours are not stated.",
        ),
    )


def test_plan_allows_only_unknown_after_capability_fit_passed() -> None:
    request = ReviewRequest(
        silver_job_id=511,
        decision="passed",
        rationale="Full-time source evidence reviewed; exact hours are not stated.",
    )
    plan = build_plan(reviews=[request], current_rows={511: _row()})

    assert plan["proposal_count"] == 1
    assert plan["blocked_count"] == 0
    proposal = plan["proposals"][0]
    assert proposal["reviewed_unknown_components"] == ["employment", "weekly_hours"]
    assert proposal["already_current"] is False
    assert plan["boundaries"]["deterministic_failed_override_allowed"] is False
    assert plan["boundaries"]["missing_source_facts_inferred"] is False


def test_plan_refuses_deterministic_failure_even_for_pass_decision() -> None:
    request = ReviewRequest(
        silver_job_id=511,
        decision="passed",
        rationale="Operator cannot override a deterministic failure.",
    )
    plan = build_plan(
        reviews=[request],
        current_rows={511: _row(deterministic="failed", employment="failed")},
    )

    assert plan["proposal_count"] == 0
    assert plan["blocked"] == [
        {
            "silver_job_id": 511,
            "decision": "passed",
            "reason": "deterministic_hard_filter_failed_cannot_be_overridden",
        }
    ]


def test_plan_refuses_unknown_when_capability_fit_is_not_passed() -> None:
    request = ReviewRequest(
        silver_job_id=511,
        decision="passed",
        rationale="Source evidence review must not replace Candidate Fact authority.",
    )
    plan = build_plan(
        reviews=[request],
        current_rows={511: _row(capability_fit="unknown")},
    )

    assert plan["proposal_count"] == 0
    assert plan["blocked"][0]["reason"] == "approved_candidate_capability_fit_required_first"


def test_duplicate_job_review_is_rejected() -> None:
    payload = {
        "schema": "job_application_pipeline.product_v1_hard_filter_review_input.v1",
        "reviews": [
            {"silver_job_id": 511, "decision": "passed", "rationale": "Reason one is long enough."},
            {"silver_job_id": 511, "decision": "failed", "rationale": "Reason two is long enough."},
        ],
    }
    with pytest.raises(HardFilterReviewStop, match="duplicate silver_job_id"):
        parse_input(payload)


def test_migration_keeps_deterministic_failure_stronger_than_review() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS product_v1_hard_filter_reviews" in source
    assert "uq_product_v1_hard_filter_review_active_job" in source
    assert "assessment_updated_at = d.assessment_updated_at" in source
    assert "r.policy_version = d.policy_version" in source
    assert "d.capability_fit_status <> 'passed'" in source
    assert "d.deterministic_hard_filter_status IN ('passed', 'failed')" in source
    assert "THEN d.deterministic_hard_filter_status" in source
    assert "review_scope = 'resolve_unknown_source_evidence'" in source
