from src.search_intelligence.product_v1_demo_origin_guard import evaluate_demo_origin_guard


def test_inactive_row_is_not_actionable_even_with_origin_url() -> None:
    result = evaluate_demo_origin_guard(
        source_url="https://jobs.example.com/job/1",
        canonical_source_type="employer_origin_career_site",
        lifecycle_status="inactive_confirmed",
        origin_validation_status="validated",
        product_readiness_status="blocked_inactive",
    )
    assert result.eligible is False
