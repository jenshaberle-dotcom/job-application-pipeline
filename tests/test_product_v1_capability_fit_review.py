from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from scripts.run_product_v1_capability_fit_review import (
    INPUT_SCHEMA,
    CandidateProfileBinding,
    CapabilityFitReviewStop,
    ReviewRequest,
    parse_input,
    validate_review_authority,
)


PROFILE_SHA = "a" * 64
DETAIL_SHA = "b" * 64


def _job_row() -> dict[str, object]:
    return {
        "origin_validation_status": "validated",
        "activity_status": "active",
        "capability_fit_status": "unknown",
        "assessment_updated_at": datetime(2026, 9, 2, 14, 0, tzinfo=UTC),
        "ranking_factors": {"detail_description_sha256": DETAIL_SHA},
        "product_readiness_status": "hard_filter_evidence_required",
        "active_review_decision": None,
        "active_review_rationale": None,
        "active_review_profile_sha256": None,
        "active_review_detail_sha256": None,
        "active_review_assessment_updated_at": None,
        "active_review_fact_keys": None,
    }


def _fact(evidence_class: str = "professional_employment") -> dict[str, object]:
    return {
        "approval_status": "approved",
        "evidence_class": evidence_class,
        "valid_from": None,
        "valid_until": None,
    }


def test_parse_requires_fact_evidence_for_pass() -> None:
    with pytest.raises(CapabilityFitReviewStop, match="requires approved Candidate Fact"):
        parse_input(
            {
                "schema": INPUT_SCHEMA,
                "candidate_profile_sha256": PROFILE_SHA,
                "reviews": [
                    {
                        "silver_job_id": 42,
                        "decision": "passed",
                        "rationale": "Reviewed against the vacancy.",
                        "candidate_fact_keys": [],
                    }
                ],
            }
        )


def test_pass_accepts_only_approved_capability_evidence() -> None:
    request = ReviewRequest(
        silver_job_id=42,
        decision="passed",
        rationale="Relevant professional evidence covers the reviewed requirement.",
        candidate_fact_keys=("employment.systems",),
    )
    plan = validate_review_authority(
        review=request,
        profile=CandidateProfileBinding("demo-v1", PROFILE_SHA),
        expected_profile_sha256=PROFILE_SHA,
        fact_rows={"employment.systems": _fact()},
        job_row=_job_row(),
        today=date(2026, 9, 2),
    )
    assert plan.would_change is True
    assert plan.referenced_fact_count == 1
    assert plan.assessment_detail_sha256 == DETAIL_SHA

    with pytest.raises(CapabilityFitReviewStop, match="not capability evidence"):
        validate_review_authority(
            review=request,
            profile=CandidateProfileBinding("demo-v1", PROFILE_SHA),
            expected_profile_sha256=PROFILE_SHA,
            fact_rows={"employment.systems": _fact("target_direction")},
            job_row=_job_row(),
            today=date(2026, 9, 2),
        )


def test_profile_and_assessment_binding_fail_closed() -> None:
    request = ReviewRequest(
        silver_job_id=42,
        decision="passed",
        rationale="Reviewed against current evidence.",
        candidate_fact_keys=("employment.systems",),
    )
    with pytest.raises(CapabilityFitReviewStop, match="profile changed"):
        validate_review_authority(
            review=request,
            profile=CandidateProfileBinding("demo-v2", "c" * 64),
            expected_profile_sha256=PROFILE_SHA,
            fact_rows={"employment.systems": _fact()},
            job_row=_job_row(),
            today=date(2026, 9, 2),
        )

    broken = _job_row()
    broken["ranking_factors"] = {}
    with pytest.raises(CapabilityFitReviewStop, match="detail fingerprint"):
        validate_review_authority(
            review=request,
            profile=CandidateProfileBinding("demo-v1", PROFILE_SHA),
            expected_profile_sha256=PROFILE_SHA,
            fact_rows={"employment.systems": _fact()},
            job_row=broken,
            today=date(2026, 9, 2),
        )


def test_exact_active_review_is_idempotent() -> None:
    assessment_at = datetime(2026, 9, 2, 14, 0, tzinfo=UTC)
    request = ReviewRequest(
        silver_job_id=42,
        decision="passed",
        rationale="Reviewed against current evidence.",
        candidate_fact_keys=("employment.systems",),
    )
    row = _job_row()
    row.update(
        {
            "capability_fit_status": "passed",
            "active_review_decision": "passed",
            "active_review_rationale": request.rationale,
            "active_review_profile_sha256": PROFILE_SHA,
            "active_review_detail_sha256": DETAIL_SHA,
            "active_review_assessment_updated_at": assessment_at,
            "active_review_fact_keys": ["employment.systems"],
        }
    )
    plan = validate_review_authority(
        review=request,
        profile=CandidateProfileBinding("demo-v1", PROFILE_SHA),
        expected_profile_sha256=PROFILE_SHA,
        fact_rows={"employment.systems": _fact()},
        job_row=row,
        today=date(2026, 9, 2),
    )
    assert plan.would_change is False
