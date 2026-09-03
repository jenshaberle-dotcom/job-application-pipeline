from src.search_intelligence.product_v1_demo_origin_guard import evaluate_demo_origin_guard


def test_missing_origin_url_is_not_actionable() -> None:
    result = evaluate_demo_origin_guard(
        source_url=None,
        canonical_source_type="employer_origin_career_site",
        lifecycle_status="active_confirmed",
        origin_validation_status="validated",
        product_readiness_status="hard_filter_evidence_required",
    )
    assert result.eligible is False
