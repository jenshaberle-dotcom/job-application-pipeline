from src.search_intelligence.product_v1_demo_origin_guard import (
    evaluate_demo_origin_guard,
)


def test_aggregator_discovery_provenance_does_not_block_verified_resolution() -> None:
    result = evaluate_demo_origin_guard(
        source_url="https://www.stepstone.de/stellenangebote/123",
        source_name="stepstone",
        canonical_source_type="aggregator",
        lifecycle_status="active_confirmed",
        origin_validation_status="validated",
        product_readiness_status="assessment_required",
        resolved_employer_origin_url="https://careers.example.com/jobs/123",
        resolved_origin_verified=True,
    )

    assert result.eligible is True
    assert result.reason == "verified_employer_origin_resolution"
    assert result.employer_origin_url == "https://careers.example.com/jobs/123"


def test_aggregator_final_action_url_still_fails_closed() -> None:
    result = evaluate_demo_origin_guard(
        source_url="https://www.stepstone.de/stellenangebote/123",
        source_name="stepstone",
        canonical_source_type="aggregator",
        lifecycle_status="active_confirmed",
        origin_validation_status="validated",
        product_readiness_status="rankable",
    )

    assert result.eligible is False
    assert result.reason == "aggregator_url_cannot_be_product_action_url"
