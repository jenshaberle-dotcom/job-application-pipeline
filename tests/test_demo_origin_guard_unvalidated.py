from src.search_intelligence.product_v1_demo_origin_guard import evaluate_demo_origin_guard


def test_unvalidated_origin_is_not_product_actionable() -> None:
    result = evaluate_demo_origin_guard(
        source_url="https://jobs.example.com/job/1",
        canonical_source_type="employer_origin_career_site",
        lifecycle_status="active_confirmed",
        origin_validation_status="unknown",
        product_readiness_status="assessment_required",
    )
    assert result.eligible is False
    assert result.reason == "employer_origin_not_validated"
