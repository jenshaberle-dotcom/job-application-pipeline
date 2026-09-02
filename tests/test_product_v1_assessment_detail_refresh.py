from __future__ import annotations

from hashlib import sha256

import pytest

from scripts.run_product_v1_assessment_detail_refresh import (
    APPROVAL_TOKEN,
    REFRESH_KEY_PREFIX,
    AssessmentDetailRefreshStop,
    build_refresh_plan,
)


SOURCE_URL = "https://example.jobs.personio.de/job/434"
OLD_DETAIL = "Permanent employee. Full-time. Remote in Germany. English required."
NEW_DETAIL = (
    "Permanent employee. Full-time. Remote in Germany. Very good English required. "
    "Build data pipelines with Python and SQL. German is a plus."
)


def _sha(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "silver_job_id": 434,
        "source_name": "personio:1komma5grad",
        "title": "(Junior) Data Engineer - Data Platform (m/f/d)",
        "source_url": SOURCE_URL,
        "lifecycle_status": "active_confirmed",
        "origin_validation_status": "validated",
        "activity_status": "active",
        "hard_filter_status": "passed",
        "profile_direction_score": 80,
        "data_focus_score": 90,
        "reliability_focus_score": 70,
        "evidence_quality_score": 75,
        "overall_quality_score": 80,
        "work_model": "remote",
        "commute_minutes": None,
        "public_transport_quality": "unknown",
        "ranking_factors": {
            "schema": "product_v1_assessment_materialization.v1",
            "detail_description_sha256": _sha(OLD_DETAIL),
            "observation_evidence_sha256": "a" * 64,
            "authority": {"profile_source_role": "employer_origin"},
        },
        "explanations": [],
        "uncertainties": [],
        "policy_key": "default",
        "policy_version": "product-v1-2026-08-18",
        "assessed_by": "deterministic_assessment_materialization_v1",
        "employment_type": "unknown",
        "employment_evidence_status": "unknown",
        "required_languages": [],
        "language_evidence_status": "unknown",
        "weekly_hours_min": None,
        "weekly_hours_max": None,
        "weekly_hours_evidence_status": "unknown",
        "salary_min_gross_eur": None,
        "salary_max_gross_eur": None,
        "salary_evidence_status": "unknown",
        "title_seniority": "junior",
        "requirements_seniority": "unknown",
        "capability_fit_status": "passed",
        "seniority_evidence_status": "unknown",
    }
    row.update(overrides)
    return row


def test_refresh_plan_is_fail_closed_on_source_authority() -> None:
    with pytest.raises(
        AssessmentDetailRefreshStop,
        match="active recurring employer-origin profile authority",
    ):
        build_refresh_plan(
            row=_row(),
            authorized_sources={"personio:eraneos"},
            final_url=SOURCE_URL,
            detail_text=NEW_DETAIL,
        )


def test_refresh_plan_rejects_cross_origin_redirect() -> None:
    with pytest.raises(AssessmentDetailRefreshStop, match="redirected outside"):
        build_refresh_plan(
            row=_row(),
            authorized_sources={"personio:1komma5grad"},
            final_url="https://aggregator.example/jobs/434",
            detail_text=NEW_DETAIL,
        )


def test_detail_drift_resets_downstream_authority_and_preserves_history_metadata() -> None:
    plan = build_refresh_plan(
        row=_row(),
        authorized_sources={"personio:1komma5grad"},
        final_url=SOURCE_URL,
        detail_text=NEW_DETAIL,
    )

    assert plan.would_change is True
    assert plan.previous_detail_sha256 == _sha(OLD_DETAIL)
    assert plan.next_detail_sha256 == _sha(NEW_DETAIL)
    assert plan.revision_key == (
        f"{REFRESH_KEY_PREFIX}:{_sha(OLD_DETAIL)[:12]}:{_sha(NEW_DETAIL)[:12]}"
    )
    assert plan.next_payload["capability_fit_status"] == "unknown"
    assert plan.next_payload["hard_filter_status"] == "unknown"
    assert plan.next_payload["profile_direction_score"] is None
    assert plan.next_payload["data_focus_score"] is None
    assert plan.next_payload["reliability_focus_score"] is None
    assert plan.next_payload["evidence_quality_score"] is None
    assert plan.next_payload["overall_quality_score"] is None

    ranking_factors = plan.next_payload["ranking_factors"]
    assert isinstance(ranking_factors, dict)
    assert ranking_factors["observation_evidence_sha256"] == "a" * 64
    assert ranking_factors["authority"] == {"profile_source_role": "employer_origin"}
    assert ranking_factors["detail_description_sha256"] == _sha(NEW_DETAIL)
    assert ranking_factors["detail_refresh"]["previous_detail_sha256"] == _sha(OLD_DETAIL)

    assert "capability_fit_status" in plan.changed_fields
    assert "hard_filter_status" in plan.changed_fields
    assert "ranking_factors" in plan.changed_fields


def test_identical_detail_does_not_request_refresh() -> None:
    plan = build_refresh_plan(
        row=_row(ranking_factors={"detail_description_sha256": _sha(NEW_DETAIL)}),
        authorized_sources={"personio:1komma5grad"},
        final_url=SOURCE_URL,
        detail_text=NEW_DETAIL,
    )

    assert plan.would_change is False
    assert plan.previous_detail_sha256 == plan.next_detail_sha256


def test_apply_token_is_stable_contract() -> None:
    assert APPROVAL_TOKEN == "PRODUCT-V1-ASSESSMENT-DETAIL-REFRESH-001"
