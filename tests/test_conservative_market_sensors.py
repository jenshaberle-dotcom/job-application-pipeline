from __future__ import annotations

from src.search_intelligence.conservative_market_sensors import (
    BOUNDARY,
    accept_provider_result,
    build_sensor_queries,
    deduplicate_observations,
)


def test_builds_site_bounded_queries_for_both_sensors() -> None:
    linkedin = build_sensor_queries(
        sensor="linkedin",
        search_terms=["Data Engineer", "ML Engineer"],
        location_signals=["Hannover"],
        max_terms=2,
        max_locations=1,
    )
    indeed = build_sensor_queries(
        sensor="indeed",
        search_terms=["Data Engineer"],
        location_signals=["Hannover"],
        max_terms=1,
        max_locations=1,
    )

    assert len(linkedin) == 2
    assert all("site:linkedin.com/jobs/view" in item.query for item in linkedin)
    assert all('"Hannover"' in item.query for item in linkedin)
    assert len(indeed) == 1
    assert "site:de.indeed.com/viewjob" in indeed[0].query


def test_accepts_only_expected_platform_host_and_job_path() -> None:
    accepted = accept_provider_result(
        sensor="linkedin",
        provider="tavily",
        query="site:linkedin.com/jobs/view data",
        url="https://www.linkedin.com/jobs/view/123456/",
        title="Data Engineer - Example GmbH",
        snippet="Example signal",
        observed_at_utc="2026-09-25T21:00:00+00:00",
    )
    assert accepted is not None
    assert accepted.authority == "discovery_only"

    assert (
        accept_provider_result(
            sensor="linkedin",
            provider="tavily",
            query="q",
            url="https://evil.example/jobs/view/123456",
            title="wrong host",
            snippet="",
            observed_at_utc="2026-09-25T21:00:00+00:00",
        )
        is None
    )
    assert (
        accept_provider_result(
            sensor="indeed",
            provider="tavily",
            query="q",
            url="https://de.indeed.com/jobs?q=data",
            title="search page",
            snippet="",
            observed_at_utc="2026-09-25T21:00:00+00:00",
        )
        is None
    )


def test_observation_is_bounded_and_deduplicated() -> None:
    one = accept_provider_result(
        sensor="indeed",
        provider="tavily",
        query="site:de.indeed.com/viewjob data",
        url="https://de.indeed.com/viewjob?jk=abc",
        title="  Data   Engineer  ",
        snippet="x" * 1000,
        observed_at_utc="2026-09-25T21:00:00+00:00",
    )
    assert one is not None
    assert one.title_signal == "Data Engineer"
    assert len(one.snippet_signal) == 500
    assert deduplicate_observations([one, one]) == (one,)


def test_sensor_boundary_has_no_product_or_platform_automation_authority() -> None:
    assert BOUNDARY["direct_platform_http_requests"] == 0
    assert BOUNDARY["login_automation"] == 0
    assert BOUNDARY["browser_automation"] == 0
    assert BOUNDARY["raw_job_content_persistence"] == 0
    assert BOUNDARY["database_writes"] == 0
    assert BOUNDARY["bronze_writes"] == 0
    assert BOUNDARY["silver_writes"] == 0
    assert BOUNDARY["product_authority"] == 0
    assert BOUNDARY["aggregator_url_is_not_origin_url"] is True
