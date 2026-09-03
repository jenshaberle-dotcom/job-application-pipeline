from src.search_intelligence.product_v1_demo_origin_guard import evaluate_demo_origin_guard


def test_actionable_origin_exposes_current_reason() -> None:
    result = evaluate_demo_origin_guard(
        source_url="https://jobs.example.com/job/1",
        canonical_source_type="employer_origin_career_site",
        lifecycle_status="active_confirmed",
        origin_validation_status="validated",
        product_readiness_status="hard_filter_evidence_required",
    )
    assert result.reason == "current_employer_origin_confirmed"
