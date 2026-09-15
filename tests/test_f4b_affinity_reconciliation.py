from decimal import Decimal

from scripts.run_f4b_affinity_reconciliation import (
    _canonical_weights_match,
    build_affinity_candidate,
    reconcile_rows,
)
from scripts.run_product_v1_ranking_score_review import RankingPolicy
from src.search_intelligence.product_v1_assessment_evidence import (
    extract_product_v1_assessment_evidence,
)


def _policy() -> RankingPolicy:
    return RankingPolicy(
        policy_version="product-v1-2026-09-03",
        weights={
            "profile_direction": Decimal("0.40"),
            "reliability_focus": Decimal("0.25"),
            "data_focus": Decimal("0.20"),
            "evidence_quality": Decimal("0.15"),
        },
        minimum_quality_score=Decimal("60"),
        top_job_limit=5,
    )


def _row(detail_text: str, **overrides: object) -> dict[str, object]:
    assessment = extract_product_v1_assessment_evidence(
        description=detail_text,
        title="Machine Learning Engineer",
        source_url="https://example.com/jobs/1",
    )
    row: dict[str, object] = {
        "silver_job_id": 1,
        "company_name": "Example GmbH",
        "title": "Machine Learning Engineer",
        "source_name": "generic_origin:example",
        "source_url": "https://example.com/jobs/1",
        "origin_validation_status": "validated",
        "activity_status": "active",
        "ranking_factors": {"detail_description_sha256": assessment.description_sha256},
    }
    row.update(overrides)
    return row


def test_affinity_candidate_does_not_require_fit_or_hard_filter_state() -> None:
    detail = "Machine learning data pipelines SQL MLOps observability automation."
    item = build_affinity_candidate(
        row=_row(detail),
        policy=_policy(),
        final_url="https://example.com/jobs/1",
        detail_text=detail,
    )
    assert item["legacy_affinity_proxy_score"] > 0
    assert item["components"]["profile_direction_score"] > 0
    assert item["authority"] == "read_only_affinity_calibration_only"


def test_reconciliation_keeps_changed_revision_out_of_affinity_candidates() -> None:
    persisted = "Machine learning SQL."
    changed = "Machine learning SQL and a materially changed detail page."

    def fetch_detail(_url: str):
        return "https://example.com/jobs/1", "Machine Learning Engineer", changed

    result = reconcile_rows(rows=[_row(persisted)], policy=_policy(), fetch_detail=fetch_detail)
    assert result["affinity_candidate_count"] == 0
    assert result["unavailable_count"] == 1
    assert result["unavailable"][0]["reason"] == "CURRENT_DETAIL_REVISION_CHANGED"


def test_canonical_pd052_weights_are_detected_without_approving_runtime_threshold() -> None:
    assert _canonical_weights_match(_policy()) is True
    drifted = RankingPolicy(
        policy_version="drift",
        weights={
            "profile_direction": Decimal("0.35"),
            "reliability_focus": Decimal("0.30"),
            "data_focus": Decimal("0.20"),
            "evidence_quality": Decimal("0.15"),
        },
        minimum_quality_score=Decimal("60"),
        top_job_limit=5,
    )
    assert _canonical_weights_match(drifted) is False
