from src.search_intelligence.product_v1_demo_origin_guard import evaluate_demo_origin_guard


def test_known_discovery_hosts_cannot_become_product_action_urls() -> None:
    for url in (
        "https://www.arbeitsagentur.de/jobsuche/jobdetail/1",
        "https://gute-jobs.de/viewjob-1",
        "https://www.stepstone.de/stellenangebote--x--1-inline.html",
    ):
        result = evaluate_demo_origin_guard(
            source_url=url,
            canonical_source_type="employer_origin_career_site",
            lifecycle_status="active_confirmed",
            origin_validation_status="validated",
            product_readiness_status="rankable",
        )
        assert result.eligible is False
