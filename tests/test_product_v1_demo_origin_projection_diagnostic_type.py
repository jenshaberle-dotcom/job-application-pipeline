from src.search_intelligence.product_v1_demo_origin_guard import (
    evaluate_demo_origin_guard,
)


def test_unknown_silver_type_does_not_veto_validated_personio_origin() -> None:
    result = evaluate_demo_origin_guard(
        source_url="https://company.jobs.personio.de/job/123?language=de",
        source_name="personio:company",
        canonical_source_type="unknown",
        lifecycle_status="active_confirmed",
        origin_validation_status="validated",
        product_readiness_status="rankable",
    )

    assert result.eligible is True
    assert result.employer_origin_url == (
        "https://company.jobs.personio.de/job/123?language=de"
    )
