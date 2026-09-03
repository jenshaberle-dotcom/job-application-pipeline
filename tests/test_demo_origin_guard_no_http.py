from src.search_intelligence.product_v1_demo_origin_guard import evaluate_demo_origin_guard


def test_plain_http_origin_is_not_demo_actionable() -> None:
    result = evaluate_demo_origin_guard(
        source_url="http://jobs.example.com/job/1",
        canonical_source_type="employer_origin_career_site",
        lifecycle_status="active_confirmed",
        origin_validation_status="validated",
        product_readiness_status="rankable",
    )
    assert result.eligible is False
    assert result.reason == "employer_origin_https_url_required"
