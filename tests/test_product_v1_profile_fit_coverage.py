from __future__ import annotations

from src.search_intelligence.product_v1_profile_fit_coverage import (
    FAILED,
    INSUFFICIENT_EVIDENCE,
    PASSED,
    PROFILE_FIT_COMPLETE,
    build_profile_fit_coverage,
    parse_candidate_geography_policy,
)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "city": "Hannover",
        "country": "Germany",
        "work_model": "remote",
        "commute_minutes": 20,
        "hard_filter_status": "passed",
        "hard_filter_reasons": {
            "employment": "passed",
            "languages": "passed",
            "weekly_hours": "passed",
            "seniority_and_capability_fit": "passed",
        },
        "profile_fit_capability_review_exact": True,
        "profile_fit_capability_review_decision": "passed",
    }
    row.update(overrides)
    return row


def test_missing_candidate_preference_is_insufficient_not_negative() -> None:
    result = build_profile_fit_coverage(_row(), candidate_preference_tags=[])

    assert result["profile_fit_coverage_status"] == INSUFFICIENT_EVIDENCE
    assert result["profile_fit_decision"] == "unknown"
    assert "geography_work_model_commute" in result["profile_fit_missing_factors"]
    assert result["profile_fit_failed_factors"] == []


def test_structured_approved_preference_and_current_evidence_can_complete_positive_fit() -> None:
    result = build_profile_fit_coverage(
        _row(),
        candidate_preference_tags=[
            "profile-fit.city.hannover",
            "profile-fit.work-model.remote",
            "profile-fit.commute.max-45",
        ],
    )

    assert result["profile_fit_coverage_status"] == PROFILE_FIT_COMPLETE
    assert result["profile_fit_decision"] == PASSED
    assert result["profile_fit_missing_factors"] == []
    assert result["profile_fit_failed_factors"] == []


def test_negative_geography_is_conclusive_and_not_misreported_as_missing() -> None:
    result = build_profile_fit_coverage(
        _row(city="Berlin"),
        candidate_preference_tags=["profile-fit.city.hannover"],
    )

    assert result["profile_fit_coverage_status"] == PROFILE_FIT_COMPLETE
    assert result["profile_fit_decision"] == FAILED
    assert "geography_work_model_commute" in result["profile_fit_failed_factors"]


def test_missing_job_evidence_under_configured_preference_remains_insufficient() -> None:
    result = build_profile_fit_coverage(
        _row(work_model="unknown", commute_minutes=None),
        candidate_preference_tags=[
            "profile-fit.work-model.remote",
            "profile-fit.commute.max-45",
        ],
    )

    assert result["profile_fit_coverage_status"] == INSUFFICIENT_EVIDENCE
    assert result["profile_fit_decision"] == "unknown"
    assert result["profile_fit_factors"]["geography_work_model_commute"]["status"] == "unknown"


def test_stale_or_missing_capability_review_never_becomes_positive_fit() -> None:
    result = build_profile_fit_coverage(
        _row(profile_fit_capability_review_exact=False),
        candidate_preference_tags=["profile-fit.city.hannover"],
    )

    assert result["profile_fit_coverage_status"] == INSUFFICIENT_EVIDENCE
    assert "skills_capabilities" in result["profile_fit_missing_factors"]
    assert "seniority" in result["profile_fit_missing_factors"]


def test_exact_negative_capability_review_is_conclusive() -> None:
    result = build_profile_fit_coverage(
        _row(
            profile_fit_capability_review_decision="failed",
            hard_filter_status="unknown",
            hard_filter_reasons={
                "employment": "manual_review_required",
                "languages": "manual_review_required",
                "weekly_hours": "manual_review_required",
                "seniority_and_capability_fit": "failed",
            },
        ),
        candidate_preference_tags=[],
    )

    assert result["profile_fit_coverage_status"] == PROFILE_FIT_COMPLETE
    assert result["profile_fit_decision"] == FAILED
    assert "skills_capabilities" in result["profile_fit_failed_factors"]


def test_hard_requirement_failure_short_circuits_without_inventing_other_evidence() -> None:
    result = build_profile_fit_coverage(
        _row(
            profile_fit_capability_review_exact=False,
            hard_filter_status="failed",
            hard_filter_reasons={
                "employment": "failed",
                "languages": "manual_review_required",
                "weekly_hours": "manual_review_required",
                "seniority_and_capability_fit": "manual_review_required",
            },
        ),
        candidate_preference_tags=[],
    )

    assert result["profile_fit_coverage_status"] == PROFILE_FIT_COMPLETE
    assert result["profile_fit_decision"] == FAILED
    assert "hard_requirements" in result["profile_fit_failed_factors"]
    assert "geography_work_model_commute" in result["profile_fit_missing_factors"]


def test_ambiguous_commute_preferences_fail_closed() -> None:
    policy = parse_candidate_geography_policy(
        ["profile-fit.commute.max-30", "profile-fit.commute.max-45"]
    )
    assert policy.valid is False
    assert policy.commute_max_minutes is None


def test_profile_fit_never_claims_ranking_top5_or_application_authority() -> None:
    result = build_profile_fit_coverage(
        _row(), candidate_preference_tags=["profile-fit.city.hannover"]
    )

    assert result["profile_fit_ranking_authority"] is False
    assert result["profile_fit_top5_authority"] is False
    assert result["profile_fit_application_authority"] is False
