from src.search_intelligence.origin_jobspace_discovery import (
    FetchedOriginPage,
    discover_official_origin_jobspace,
)
from src.search_intelligence.origin_source_discovery_agent import (
    OriginDiscoveryProbeResult,
    OriginSearchResult,
)


def accepted_probe(url: str) -> OriginDiscoveryProbeResult:
    return OriginDiscoveryProbeResult(
        url=url,
        final_url=url,
        status_code=200,
        reachable=True,
        career_like=(
            "career" in url.casefold()
            or "karriere" in url.casefold()
            or "job" in url.casefold()
            or "myworkdayjobs.com" in url.casefold()
        ),
        reason="fake bounded probe",
    )


def test_official_company_page_can_lead_to_linked_ats_jobspace() -> None:
    official = "https://www.neutral-example.de/karriere"
    workday = "https://wd3.myworkdayjobs.com/NeutralExample_Careers"

    def fetch_page(url: str) -> FetchedOriginPage:
        assert url == official
        return FetchedOriginPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            html=f'<html><body><a href="{workday}">Offene Stellen</a></body></html>',
        )

    result = discover_official_origin_jobspace(
        company_key="neutral_example",
        company_name="Neutral Example GmbH",
        search_results=(
            OriginSearchResult(
                url=official,
                title="Neutral Example Karriere",
                snippet="Offizielle Karriere-Seite der Neutral Example GmbH",
                provider="test_search",
            ),
        ),
        probe=accepted_probe,
        fetch_page=fetch_page,
        max_generated_candidates=0,
    )

    assert result.initial.selected_url == official
    assert result.surface_page_count == 1
    assert result.discovered_jobspace_url_count == 1
    assert result.ats_families == ("workday",)
    assert result.origin.decision == "origin_url_candidate_selected"
    assert any(
        item.candidate.url == workday
        and item.candidate.provider == "search_provider_candidate"
        for item in result.origin.alternatives
    )


def test_official_domain_evidence_does_not_bypass_identity_or_reachability() -> None:
    wrong = "https://www.completely-unrelated.example/karriere"

    def rejecting_probe(url: str) -> OriginDiscoveryProbeResult:
        return OriginDiscoveryProbeResult(
            url=url,
            final_url=url,
            status_code=404,
            reachable=False,
            career_like=True,
            reason="fake unreachable",
        )

    result = discover_official_origin_jobspace(
        company_key="neutral_example",
        company_name="Neutral Example GmbH",
        official_domain_urls=(wrong,),
        probe=rejecting_probe,
        fetch_page=None,
        max_generated_candidates=0,
    )

    assert result.official_domain_evidence_count == 1
    assert result.origin.decision == "not_found"
    assert result.origin.selected_url is None


def test_surface_expansion_is_bounded_to_three_plausible_pages() -> None:
    candidates = tuple(
        OriginSearchResult(
            url=f"https://neutral-example.de/karriere/{index}",
            title="Neutral Example Karriere",
            snippet="Neutral Example GmbH Jobs",
            provider="test_search",
        )
        for index in range(6)
    )
    fetched: list[str] = []

    def fetch_page(url: str) -> FetchedOriginPage:
        fetched.append(url)
        return FetchedOriginPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            html="<html><body><a href='/about'>About</a></body></html>",
        )

    result = discover_official_origin_jobspace(
        company_key="neutral_example",
        company_name="Neutral Example GmbH",
        search_results=candidates,
        probe=accepted_probe,
        fetch_page=fetch_page,
        max_generated_candidates=0,
    )

    assert result.surface_page_count == 3
    assert len(fetched) == 3
    assert result.discovered_jobspace_url_count == 0


def test_script_text_cannot_seed_a_fake_ats_jobspace() -> None:
    official = "https://neutral-example.de/karriere"

    def fetch_page(url: str) -> FetchedOriginPage:
        return FetchedOriginPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            html="""
                <html><body>
                <script>const fake='https://jobs.lever.co/wrong-company';</script>
                <p>We once evaluated Greenhouse.</p>
                </body></html>
            """,
        )

    result = discover_official_origin_jobspace(
        company_key="neutral_example",
        company_name="Neutral Example GmbH",
        search_results=(
            OriginSearchResult(
                url=official,
                title="Neutral Example Karriere",
                snippet="Neutral Example GmbH Jobs",
                provider="test_search",
            ),
        ),
        probe=accepted_probe,
        fetch_page=fetch_page,
        max_generated_candidates=0,
    )

    assert result.ats_families == ()
    assert result.discovered_jobspace_url_count == 0
