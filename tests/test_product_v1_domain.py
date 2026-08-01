from __future__ import annotations

import pytest

from src.search_intelligence.product_v1 import (
    ApplicationSourceDocument,
    OperatorDecisionRequired,
    ProductJob,
    RankingPolicy,
    build_application_source_manifest,
    product_readiness_status,
    rank_product_jobs,
)
from src.search_intelligence.product_v1_policy import (
    HardFilterPolicy,
    JobConstraintEvidence,
    evaluate_hard_filters,
)


def job(**overrides: object) -> ProductJob:
    values: dict[str, object] = {
        "silver_job_id": 1,
        "title": "Machine Learning Engineer",
        "company_name": "Example GmbH",
        "source_url": "https://example.com/jobs/1",
        "origin_validation_status": "validated",
        "activity_status": "active",
        "hard_filter_status": "passed",
        "profile_direction_score": 90.0,
        "data_focus_score": 85.0,
        "reliability_focus_score": 80.0,
        "evidence_quality_score": 95.0,
        "work_model": "remote",
        "commute_minutes": None,
        "public_transport_quality": "unknown",
    }
    values.update(overrides)
    return ProductJob(**values)


def approved_policy(**overrides: object) -> RankingPolicy:
    values: dict[str, object] = {
        "status": "approved",
        "top_job_limit": 5,
        "minimum_quality_score": 70.0,
        "factor_weights": {
            "profile_direction": 0.40,
            "reliability_focus": 0.25,
            "data_focus": 0.20,
            "evidence_quality": 0.15,
        },
        "comparable_score_delta": 3.0,
        "explanation_mode": "score_components_reasons_uncertainties_missing_information",
        "policy_version": "product-v1-2026-08-02",
    }
    values.update(overrides)
    return RankingPolicy(**values)


def passing_constraints(**overrides: object) -> JobConstraintEvidence:
    values: dict[str, object] = {
        "employment_type": "permanent",
        "employment_evidence_status": "observed",
        "required_languages": ("de", "en"),
        "language_evidence_status": "observed",
        "weekly_hours_min": 35.0,
        "weekly_hours_max": 40.0,
        "weekly_hours_evidence_status": "observed",
        "salary_min_gross_eur": 70_000,
        "salary_max_gross_eur": 80_000,
        "salary_evidence_status": "observed",
        "title_seniority": "senior",
        "requirements_seniority": "senior",
        "capability_fit_status": "passed",
        "seniority_evidence_status": "observed",
    }
    values.update(overrides)
    return JobConstraintEvidence(**values)


def test_product_readiness_requires_origin_activity_and_hard_filter_truth() -> None:
    assert product_readiness_status(job()) == "rankable"
    assert (
        product_readiness_status(job(origin_validation_status="pending"))
        == "origin_validation_required"
    )
    assert (
        product_readiness_status(job(activity_status="unknown"))
        == "activity_evidence_required"
    )
    assert (
        product_readiness_status(job(hard_filter_status="unknown"))
        == "hard_filter_evidence_required"
    )
    assert (
        product_readiness_status(job(hard_filter_status="failed"))
        == "blocked_hard_filter"
    )


def test_ranking_refuses_to_guess_open_operator_decisions() -> None:
    policy = RankingPolicy(
        status="operator_decision_required",
        top_job_limit=None,
        minimum_quality_score=None,
    )

    with pytest.raises(OperatorDecisionRequired, match="Operator decisions required"):
        rank_product_jobs([job()], policy)


def test_approved_policy_uses_the_operator_selected_start_configuration() -> None:
    policy = approved_policy()

    policy.require_approved()
    assert policy.top_job_limit == 5
    assert policy.minimum_quality_score == 70.0
    assert policy.comparable_score_delta == 3.0
    assert policy.factor_weights == {
        "profile_direction": 0.40,
        "reliability_focus": 0.25,
        "data_focus": 0.20,
        "evidence_quality": 0.15,
    }


def test_stronger_profile_direction_outranks_hybrid_when_not_comparable() -> None:
    stronger_remote = job(
        silver_job_id=1,
        company_name="Strong Remote",
        profile_direction_score=98,
        reliability_focus_score=95,
        work_model="remote",
    )
    weaker_hybrid = job(
        silver_job_id=2,
        company_name="Weaker Hybrid",
        profile_direction_score=75,
        reliability_focus_score=65,
        work_model="hybrid",
        commute_minutes=25,
        public_transport_quality="good",
    )

    ranked = rank_product_jobs([weaker_hybrid, stronger_remote], approved_policy())

    assert [item.job.company_name for item in ranked] == [
        "Strong Remote",
        "Weaker Hybrid",
    ]


def test_hybrid_wins_only_inside_comparable_score_range() -> None:
    remote = job(
        silver_job_id=1,
        company_name="Remote",
        evidence_quality_score=95,
        work_model="remote",
    )
    hybrid = job(
        silver_job_id=2,
        company_name="Hybrid",
        evidence_quality_score=94,
        work_model="hybrid",
        commute_minutes=35,
    )

    ranked = rank_product_jobs([remote, hybrid], approved_policy())

    assert [item.job.company_name for item in ranked] == ["Hybrid", "Remote"]
    assert "Hybrid preference" in " ".join(ranked[0].ranking_reasons)


def test_ranking_uses_threshold_and_limit_without_filling_with_blocked_jobs() -> None:
    eligible = job(silver_job_id=1)
    below_threshold = job(
        silver_job_id=2,
        profile_direction_score=10,
        data_focus_score=10,
        reliability_focus_score=10,
        evidence_quality_score=10,
    )
    unvalidated = job(silver_job_id=3, origin_validation_status="pending")

    ranked = rank_product_jobs(
        [eligible, below_threshold, unvalidated],
        approved_policy(),
    )

    assert [item.job.silver_job_id for item in ranked] == [1]
    assert ranked[0].overall_quality_score == 87.25


def test_senior_title_is_allowed_when_actual_requirements_and_capabilities_fit() -> None:
    result = evaluate_hard_filters(
        passing_constraints(
            title_seniority="senior",
            requirements_seniority="senior",
            capability_fit_status="passed",
        )
    )

    assert result.status == "passed"
    assert result.seniority_status == "passed"


def test_junior_title_with_senior_requirements_is_rejected() -> None:
    result = evaluate_hard_filters(
        passing_constraints(
            title_seniority="junior",
            requirements_seniority="senior",
            capability_fit_status="passed",
        )
    )

    assert result.status == "failed"
    assert result.seniority_status == "failed"


def test_permanent_german_english_and_35_to_40_hours_pass() -> None:
    result = evaluate_hard_filters(passing_constraints())

    assert result.status == "passed"
    assert result.employment_status == "passed"
    assert result.language_status == "passed"
    assert result.weekly_hours_status == "passed"


def test_non_permanent_extra_language_or_incompatible_hours_fail() -> None:
    assert (
        evaluate_hard_filters(
            passing_constraints(employment_type="fixed_term")
        ).status
        == "failed"
    )
    assert (
        evaluate_hard_filters(
            passing_constraints(required_languages=("de", "en", "fr"))
        ).status
        == "failed"
    )
    assert (
        evaluate_hard_filters(
            passing_constraints(weekly_hours_min=30, weekly_hours_max=32)
        ).status
        == "failed"
    )


def test_salary_target_is_soft_and_does_not_reject_an_otherwise_suitable_job() -> None:
    result = evaluate_hard_filters(
        passing_constraints(
            salary_min_gross_eur=60_000,
            salary_max_gross_eur=68_000,
        ),
        HardFilterPolicy(target_salary_gross_eur=75_000),
    )

    assert result.status == "passed"
    assert result.salary_signal == "below_target_review"


def test_missing_required_filter_evidence_stays_review_required() -> None:
    result = evaluate_hard_filters(JobConstraintEvidence())

    assert result.status == "unknown"
    assert "manual_review_required" in result.reasons[0]


def test_application_manifest_requires_approved_cv_and_base_letter() -> None:
    only_cv = ApplicationSourceDocument(
        document_type="base_cv",
        source_label="Canonical CV",
        source_reference="operator://cv/base",
        content_sha256="a" * 64,
        status="approved",
    )

    blocked = build_application_source_manifest(
        job=job(), source_documents=[only_cv]
    )

    assert blocked.status == "blocked"
    assert blocked.blockers == ("missing_approved_base_application_letter",)
    assert blocked.manifest_sha256 is None


def test_application_manifest_is_stable_and_source_grounded() -> None:
    documents = [
        ApplicationSourceDocument(
            document_type="base_cv",
            source_label="Canonical CV",
            source_reference="operator://cv/base",
            content_sha256="a" * 64,
            status="approved",
        ),
        ApplicationSourceDocument(
            document_type="base_application_letter",
            source_label="Canonical letter",
            source_reference="operator://letter/base",
            content_sha256="b" * 64,
            status="approved",
        ),
    ]

    first = build_application_source_manifest(
        job=job(), source_documents=documents
    )
    second = build_application_source_manifest(
        job=job(), source_documents=list(reversed(documents))
    )

    assert first.status == "ready_for_generation"
    assert first.manifest_sha256 == second.manifest_sha256
    assert first.blockers == ()
