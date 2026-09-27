from __future__ import annotations

from pathlib import Path

from src.search_intelligence.conservative_market_sensors import (
    BOUNDARY,
    accept_provider_result,
    build_sensor_queries,
    deduplicate_observations,
    extract_observed_company_signal,
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


def test_persisted_observation_omits_platform_content() -> None:
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

    persisted = one.as_dict()
    assert "url" not in persisted
    assert "title_signal" not in persisted
    assert "snippet_signal" not in persisted
    assert len(str(persisted["platform_reference_sha256"])) == 64
    assert "abc" not in str(persisted["platform_reference_sha256"])


def test_sensor_boundary_has_no_product_or_platform_automation_authority() -> None:
    assert BOUNDARY["direct_platform_http_requests"] == 0
    assert BOUNDARY["login_automation"] == 0
    assert BOUNDARY["browser_automation"] == 0
    assert BOUNDARY["raw_job_content_persistence"] == 0
    assert BOUNDARY["anti_bot_evasion"] == 0
    assert BOUNDARY["proxy_rotation"] == 0
    assert BOUNDARY["unofficial_platform_api"] == 0
    assert BOUNDARY["direct_guest_api"] == 0
    assert BOUNDARY["member_profile_access"] == 0
    assert BOUNDARY["personal_data_targeting"] == 0
    assert BOUNDARY["platform_url_persistence"] == 0
    assert BOUNDARY["platform_title_persistence"] == 0
    assert BOUNDARY["platform_snippet_persistence"] == 0
    assert BOUNDARY["provider_raw_content_requests"] == 0
    assert BOUNDARY["provider_query_personal_data"] == 0
    assert BOUNDARY["database_writes"] == 0
    assert BOUNDARY["bronze_writes"] == 0
    assert BOUNDARY["silver_writes"] == 0
    assert BOUNDARY["product_authority"] == 0
    assert BOUNDARY["aggregator_url_is_not_origin_url"] is True


def test_extracts_only_explicit_company_signals() -> None:
    company, rule = extract_observed_company_signal(
        sensor="linkedin",
        title="HDI Group sucht Algorithmic Cyber Portfolio Steerer / AI-Engineer",
        snippet="",
    )
    assert company == "HDI Group"
    assert rule == "linkedin_title_company_prefix"

    company, rule = extract_observed_company_signal(
        sensor="indeed",
        title="Consultant GenAI & Agentic AI | Insurance (m/w/d)",
        snippet=(
            "Consultant GenAI & Agentic AI | Insurance (m/w/d) "
            "Deloitte GmbH · 3.9 Hannover Stellenbeschreibung"
        ),
    )
    assert company == "Deloitte GmbH"
    assert rule == "indeed_title_prefix_rating"


def test_company_signal_stays_unknown_when_result_metadata_is_ambiguous() -> None:
    company, rule = extract_observed_company_signal(
        sensor="linkedin",
        title="Senior AI Engineer (m/f/d)",
        snippet="Get notified about new Artificial Intelligence Engineer jobs in Hannover.",
    )
    assert company is None
    assert rule is None


def test_accepted_observation_carries_explicit_company_and_intent() -> None:
    observation = accept_provider_result(
        sensor="linkedin",
        provider="tavily",
        query='site:linkedin.com/jobs/view "AI Architect" "Hannover" Germany',
        url="https://www.linkedin.com/jobs/view/123456/",
        title="AI Consumer Experience Manager bei Sonova Gruppe",
        snippet="Bewerben Sie sich für die Stelle in Hannover.",
        observed_at_utc="2026-09-26T10:31:57+00:00",
        search_term="AI Architect",
        location_signal="Hannover",
    )
    assert observation is not None
    assert observation.search_term == "AI Architect"
    assert observation.location_signal == "Hannover"
    assert observation.observed_company_signal == "Sonova Gruppe"
    assert observation.company_signal_status == "explicit"


def test_active_sensor_implementation_has_no_direct_linkedin_transport_stack() -> None:
    module = Path("src/search_intelligence/conservative_market_sensors.py").read_text(
        encoding="utf-8"
    )
    runner = Path("scripts/run_freeze2_linkedin_indeed_market_sensors.py").read_text(
        encoding="utf-8"
    )
    active = module + "\n" + runner

    for forbidden in (
        "import requests",
        "from requests",
        "import httpx",
        "from httpx",
        "import aiohttp",
        "from aiohttp",
        "selenium",
        "playwright",
        "/voyager/api",
        "/jobs-guest/",
        "/uas/authenticate",
    ):
        assert forbidden not in active

    assert "duckduckgo_html_search(" in runner
    assert "tavily_search(" in runner
    assert 'default="duckduckgo_html"' in runner
    assert "site:linkedin.com/jobs/view" in module


def test_provider_path_stays_basic_without_raw_content_requests() -> None:
    runner = Path("scripts/run_freeze2_linkedin_indeed_market_sensors.py").read_text(
        encoding="utf-8"
    )
    provider = Path("scripts/run_origin_source_discovery_agent.py").read_text(
        encoding="utf-8"
    )

    assert 'search_depth="basic"' in runner
    assert '"include_answer": False' in provider
    assert '"include_raw_content": False' in provider
    assert "extract_depth" not in runner


def test_paid_provider_is_explicit_optional_fallback_not_default() -> None:
    runner = Path("scripts/run_freeze2_linkedin_indeed_market_sensors.py").read_text(
        encoding="utf-8"
    )
    workflow = Path(
        ".github/workflows/freeze2-linkedin-indeed-market-sensors.yml"
    ).read_text(encoding="utf-8")

    assert 'choices=("none", "duckduckgo_html", "tavily")' in runner
    assert 'default="duckduckgo_html"' in runner
    assert '"automatic_paid_fallback": False' in runner
    assert "default: duckduckgo_html" in workflow
    assert "PAID_PROVIDER_OPT_IN=YES" in workflow
    assert '--provider "$SEARCH_BACKEND"' in workflow
    assert "--provider tavily" not in workflow
