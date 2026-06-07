from src.search_intelligence.origin_source_discovery_agent import (
    OriginDiscoveryProbeResult,
    discover_origin_source,
)


def fake_probe(url: str) -> OriginDiscoveryProbeResult:
    return OriginDiscoveryProbeResult(
        url=url,
        final_url=url,
        status_code=200,
        reachable=True,
        career_like=True,
        response_bytes=1024,
        title="Fake reachable career page",
        reason="fake reachable career-like URL",
    )


def test_ranking_prefers_corporate_origin_over_jobboard_when_both_select() -> None:
    result = discover_origin_source(
        company_key="technische_informationsbibliothek_tib",
        company_name="Technische Informationsbibliothek (TIB)",
        search_results=[
            {
                "url": "https://www.myability.jobs/de/jobs/hannover/technische-informationsbibliothek-tib",
                "title": "Technische Informationsbibliothek (TIB) Jobs in Hannover",
                "snippet": "Karriere Jobs",
                "query": '"Technische Informationsbibliothek (TIB)" Karriere Jobs Hannover',
                "provider": "test",
            },
            {
                "url": "https://www.tib.eu/de/die-tib/karriere-und-ausbildung",
                "title": "Karriere und Ausbildung - TIB.eu",
                "snippet": "Technische Informationsbibliothek Karriere",
                "query": '"Technische Informationsbibliothek (TIB)" Karriere Jobs Hannover',
                "provider": "test",
            },
        ],
        probe=fake_probe,
    )

    assert result.selected_url == "https://www.tib.eu/de/die-tib/karriere-und-ausbildung"


def test_ranking_prefers_stronger_corporate_identity_over_workwise() -> None:
    result = discover_origin_source(
        company_key="wertgarantie",
        company_name="WERTGARANTIE Group",
        search_results=[
            {
                "url": "https://www.workwise.io/unternehmen/71900-wertgarantie-group",
                "title": "Karriere und Jobs bei WERTGARANTIE Group",
                "snippet": "WERTGARANTIE Group Karriere",
                "query": '"WERTGARANTIE Group" Karriere Jobs Hannover',
                "provider": "test",
            },
            {
                "url": "https://wertgarantie-group.com/karriere",
                "title": "Karriere WERTGARANTIE Group",
                "snippet": "WERTGARANTIE Group Karriere",
                "query": '"WERTGARANTIE Group" Karriere Jobs Hannover',
                "provider": "test",
            },
        ],
        probe=fake_probe,
    )

    assert result.selected_url == "https://wertgarantie-group.com/karriere"
