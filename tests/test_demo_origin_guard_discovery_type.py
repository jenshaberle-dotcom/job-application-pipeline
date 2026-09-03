from src.search_intelligence.product_v1_demo_origin_guard import evaluate_demo_origin_guard


def test_discovery_type_is_not_actionable() -> None:
    result = evaluate_demo_origin_guard(
        source_url="https://jobs.example.com/job/1",
        canonical_source_type="aggregator",
        lifecycle_status="active_confirmed",
        origin_validation_status="validated",
        product_readiness_status="rankable",
    )
    assert result.eligible is False
