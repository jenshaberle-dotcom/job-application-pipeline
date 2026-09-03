from src.search_intelligence.product_v1_demo_origin_guard import evaluate_demo_origin_guard


def test_gute_jobs_is_discovery_only() -> None:
    result = evaluate_demo_origin_guard(
        source_url="https://gute-jobs.de/viewjob-x",
        canonical_source_type="employer_origin_career_site",
        lifecycle_status="active_confirmed",
        origin_validation_status="validated",
        product_readiness_status="rankable",
    )
    assert result.eligible is False
