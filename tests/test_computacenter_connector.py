from __future__ import annotations

from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.computacenter import (
    COMPANY_NAME,
    SOURCE_NAME,
    SOURCE_TYPE,
    ComputacenterConnector,
    extract_candidate_links,
    is_structural_job_detail_url,
    select_detail_candidates,
)


LISTING_URL = 'https://jobs.computacenter.com/search/?searchby=location&q=&locationsearch=&geolocation=&optionsFacetsDD_country=&optionsFacetsDD_city='
DETAIL_URL = 'https://jobs.computacenter.com/job/Hannover-Product-Owner-Data-Platform-30159/1412345678/'
COOKIE_URL = 'https://jobs.computacenter.com/content/Cookie-Policy/?locale=en_GB'
SEARCH_URL = 'https://jobs.computacenter.com/search/?searchby=location&q=data&locationsearch=Hannover'


def fake_fetcher(url: str) -> tuple[str, str, int]:
    if url == LISTING_URL:
        html = (
            "<html><body>"
            f"<a href='{DETAIL_URL}'>Product Owner Data Platform Hannover</a>"
            "<a href='/job/Hannover-Duales-Studium-Data-30159/1411111111/'>Duales Studium Data Hannover</a>"
            "</body></html>"
        )
        return html, LISTING_URL, 200

    if url == DETAIL_URL:
        html = (
            "<html>"
            "<title>Product Owner Data Platform</title>"
            "<body>Product Owner Data Platform in Hannover. Data, Analytics and stakeholder work.</body>"
            "</html>"
        )
        return html, DETAIL_URL, 200

    raise AssertionError(f"Unexpected URL: {url}")


def make_profile() -> SearchProfile:
    return SearchProfile(
        id=1,
        profile_name="unit_test",
        source_name=SOURCE_NAME,
        search_location="Hannover",
        search_radius_km=50,
        offer_type=None,
        page_size=10,
    )


def test_structural_job_detail_url_matches_real_computacenter_shape_only() -> None:
    assert is_structural_job_detail_url(DETAIL_URL) is True
    assert is_structural_job_detail_url(COOKIE_URL) is False
    assert is_structural_job_detail_url(SEARCH_URL) is False
    assert is_structural_job_detail_url("https://example.com/job/test/123/") is False


def test_extract_candidate_links_is_bounded_to_relevant_same_domain_job_links() -> None:
    html, final_url, _ = fake_fetcher(LISTING_URL)

    candidates = extract_candidate_links(html, final_url)
    selected = select_detail_candidates(candidates, limit=3)

    assert [candidate.url for candidate in selected] == [DETAIL_URL]


def test_extract_candidate_links_rejects_content_and_search_false_positives() -> None:
    html = (
        "<html><body>"
        f"<a href='{COOKIE_URL}'>Data Analytics Hannover privacy information</a>"
        f"<a href='{SEARCH_URL}'>Data Analytics jobs Hannover</a>"
        f"<a href='{DETAIL_URL}'>Product Owner Data Platform Hannover</a>"
        "</body></html>"
    )

    candidates = extract_candidate_links(html, LISTING_URL)

    assert [candidate.url for candidate in candidates] == [DETAIL_URL]


def test_connector_fetches_bounded_relevant_jobs() -> None:
    connector = ComputacenterConnector(listing_url=LISTING_URL, fetcher=fake_fetcher)

    records, final_url = connector.fetch_jobs(
        profile=make_profile(),
        search_term=SearchTerm("Product Owner", id=1),
    )

    assert final_url == LISTING_URL
    assert len(records) == 1

    record = records[0]
    assert record.source_name == SOURCE_NAME
    assert record.source_url == DETAIL_URL
    assert record.external_job_id
    assert record.raw_data["source_type"] == SOURCE_TYPE
    assert record.raw_data["source_family"]
    assert record.raw_data["result_card"]["company_name"] == COMPANY_NAME
    assert "Product Owner" in record.raw_data["result_card"]["title"]
    assert record.raw_data["acquisition_boundary"]["browser_automation_used"] is False
    assert record.raw_data["acquisition_boundary"]["raw_html_persisted"] is False


def test_connector_rejects_redirect_from_job_detail_to_search_page() -> None:
    def redirecting_fetcher(url: str) -> tuple[str, str, int]:
        if url == LISTING_URL:
            return (
                f"<html><body><a href='{DETAIL_URL}'>Data Platform Hannover</a></body></html>",
                LISTING_URL,
                200,
            )
        if url == DETAIL_URL:
            return (
                "<html><title>Data Jobs Hannover</title><body>Data Analytics Hannover</body></html>",
                SEARCH_URL,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    connector = ComputacenterConnector(listing_url=LISTING_URL, fetcher=redirecting_fetcher)

    records, final_url = connector.fetch_jobs(
        profile=make_profile(),
        search_term=SearchTerm("Data", id=1),
    )

    assert final_url == LISTING_URL
    assert records == []
