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
        "minimum_quality_score": 60.0,
        "factor_weights": {
            "profile_direction": 5,
            "data_focus": 3,
            "reliability_focus": 4,
            "evidence_quality": 2,
        },
        "comparable_score_delta": 2.0,
        "explanation_mode": "reasons_and_uncertainty",
        "policy_version": "test-v1",
    }
    values.update(overrides)
    return RankingPolicy(**values)


def test_product_readiness_requires_origin_activity_and_hard_filter_truth() -> None:
    assert product_readiness_status(job()) == "rankable"
    assert product_readiness_status(job(origin_validation_status="pending")) == "origin_validation_required"
    assert product_readiness_status(job(activity_status="unknown")) == "activity_evidence_required"
    assert product_readiness_status(job(hard_filter_status="unknown")) == "hard_filter_decision_required"
    assert product_readiness_status(job(hard_filter_status="failed")) == "blocked_hard_filter"


def test_ranking_refuses_to_guess_open_operator_decisions() -> None:
    policy = RankingPolicy(
        status="operator_decision_required",
        top_job_limit=None,
        minimum_quality_score=None,
    )

    with pytest.raises(OperatorDecisionRequired, match="Operator decisions required"):
        rank_product_jobs([job()], policy)


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

    assert [item.job.company_name for item in ranked] == ["Strong Remote", "Weaker Hybrid"]


def test_hybrid_wins_only_inside_comparable_score_range() -> None:
    remote = job(
        silver_job_id=1,
        company_name="Remote",
        profile_direction_score=90,
        data_focus_score=85,
        reliability_focus_score=80,
        evidence_quality_score=95,
        work_model="remote",
    )
    hybrid = job(
        silver_job_id=2,
        company_name="Hybrid",
        profile_direction_score=90,
        data_focus_score=85,
        reliability_focus_score=80,
        evidence_quality_score=94,
        work_model="hybrid",
        commute_minutes=35,
    )

    ranked = rank_product_jobs([remote, hybrid], approved_policy(comparable_score_delta=2.0))

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
        approved_policy(top_job_limit=5, minimum_quality_score=60),
    )

    assert [item.job.silver_job_id for item in ranked] == [1]


def test_application_manifest_requires_approved_cv_and_base_letter() -> None:
    only_cv = ApplicationSourceDocument(
        document_type="base_cv",
        source_label="Canonical CV",
        source_reference="operator://cv/base",
        content_sha256="a" * 64,
        status="approved",
    )

    blocked = build_application_source_manifest(job=job(), source_documents=[only_cv])

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

    first = build_application_source_manifest(job=job(), source_documents=documents)
    second = build_application_source_manifest(job=job(), source_documents=list(reversed(documents)))

    assert first.status == "ready_for_generation"
    assert first.manifest_sha256 == second.manifest_sha256
    assert first.blockers == ()
