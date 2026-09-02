from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.run_product_v1_ranking_score_review import (
    RankingPolicy,
    RankingScoreReviewStop,
    build_plan_item,
    calculate_overall_quality_score,
    validate_current_authority,
    validate_policy,
)


DETAIL = (
    "Permanent employment. Hybrid work model. Fluent German and English. "
    "35-40 hours per week. We require a senior-level professional. "
    "Build data pipelines with SQL, reliability, observability and Terraform."
)


def _policy() -> RankingPolicy:
    return RankingPolicy(
        policy_version="product-v1-2026-08-02",
        weights={
            "profile_direction": Decimal("0.40"),
            "reliability_focus": Decimal("0.25"),
            "data_focus": Decimal("0.20"),
            "evidence_quality": Decimal("0.15"),
        },
        minimum_quality_score=Decimal("70.00"),
        top_job_limit=5,
    )


def _policy_row() -> dict[str, object]:
    return {
        "status": "approved",
        "policy_version": "product-v1-2026-08-02",
        "ranking_weights": {
            "profile_direction": 0.40,
            "reliability_focus": 0.25,
            "data_focus": 0.20,
            "evidence_quality": 0.15,
        },
        "minimum_quality_score": 70,
        "top_job_limit": 5,
    }


def _row(detail_sha: str) -> dict[str, object]:
    return {
        "silver_job_id": 42,
        "title": "Senior Data Engineer",
        "source_url": "https://jobs.example.com/jobs/42",
        "origin_validation_status": "validated",
        "activity_status": "active",
        "capability_fit_status": "passed",
        "hard_filter_status": "passed",
        "assessment_updated_at": datetime(2026, 9, 2, 14, 0, tzinfo=UTC),
        "ranking_factors": {"detail_description_sha256": detail_sha},
        "profile_direction_score": None,
        "data_focus_score": None,
        "reliability_focus_score": None,
        "evidence_quality_score": None,
        "overall_quality_score": None,
        "active_review_assessment_updated_at": None,
        "active_review_detail_sha256": None,
        "active_review_policy_version": None,
        "active_review_rubric_version": None,
        "active_review_component_scores": None,
        "active_review_overall_quality_score": None,
    }


def test_policy_requires_exact_positive_weight_contract() -> None:
    policy = validate_policy(_policy_row())
    assert policy.top_job_limit == 5
    assert policy.minimum_quality_score == Decimal("70")

    broken = _policy_row()
    broken["ranking_weights"] = {
        "profile_direction": 0.40,
        "reliability_focus": 0.25,
        "data_focus": 0.20,
    }
    with pytest.raises(RankingScoreReviewStop, match="weight keys"):
        validate_policy(broken)

    broken = _policy_row()
    broken["ranking_weights"] = {
        "profile_direction": 0.40,
        "reliability_focus": -0.25,
        "data_focus": 0.20,
        "evidence_quality": 0.15,
    }
    with pytest.raises(RankingScoreReviewStop, match="must be positive"):
        validate_policy(broken)


def test_overall_score_uses_approved_weights_only() -> None:
    score = calculate_overall_quality_score(
        {
            "profile_direction_score": 80,
            "reliability_focus_score": 60,
            "data_focus_score": 50,
            "evidence_quality_score": 100,
        },
        _policy(),
    )
    assert score == Decimal("72.00")


def test_current_authority_requires_all_upstream_product_gates() -> None:
    row = _row("a" * 64)
    assessment_at, detail_sha = validate_current_authority(row)
    assert assessment_at == row["assessment_updated_at"]
    assert detail_sha == "a" * 64

    for key, value, message in (
        ("origin_validation_status", "pending", "origin"),
        ("activity_status", "unknown", "active"),
        ("capability_fit_status", "unknown", "capability"),
        ("hard_filter_status", "unknown", "hard-filter"),
    ):
        broken = dict(row)
        broken[key] = value
        with pytest.raises(RankingScoreReviewStop, match=message):
            validate_current_authority(broken)


def test_plan_is_bound_to_exact_materialized_detail_hash() -> None:
    from src.search_intelligence.product_v1_assessment_evidence import (
        extract_product_v1_assessment_evidence,
    )

    source_url = "https://jobs.example.com/jobs/42"
    detail_sha = extract_product_v1_assessment_evidence(
        description=DETAIL,
        title="Senior Data Engineer",
        source_url=source_url,
    ).description_sha256
    row = _row(detail_sha)
    item = build_plan_item(
        row=row,
        policy=_policy(),
        final_url=source_url,
        detail_text=DETAIL,
    )
    assert item.assessment_detail_sha256 == detail_sha
    assert item.overall_quality_score >= Decimal("0")
    assert item.overall_quality_score <= Decimal("100")
    assert item.evidence_payload["ranking_authority"] is False
    assert item.evidence_payload["product_authority"] is False
    assert item.would_change is True

    with pytest.raises(RankingScoreReviewStop, match="detail evidence changed"):
        build_plan_item(
            row=_row("b" * 64),
            policy=_policy(),
            final_url=source_url,
            detail_text=DETAIL,
        )


def test_ranking_write_has_separate_revision_clock() -> None:
    source = Path("scripts/run_product_v1_ranking_score_review.py").read_text(
        encoding="utf-8"
    )
    marker = "UPDATE job_product_assessments"
    start = source.index(marker)
    statement = source[start : source.index('"""', start)]
    assert "ranking_updated_at = now()" in statement
    assert "updated_at = now()" not in statement.replace("ranking_updated_at = now()", "")
    assert "capability_fit_status =" not in statement
    assert "hard_filter_status =" not in statement
