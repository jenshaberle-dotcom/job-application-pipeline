from __future__ import annotations

from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.hdi import (
    COMPANY_NAME,
    SOURCE_NAME,
    SOURCE_TYPE,
    HdiConnector,
    decode_response_text,
    is_concrete_job_detail_url,
    extract_candidate_links,
    select_detail_candidates,
)


LISTING_URL = 'https://careers.hdi.group/en/your_career_opportunities/job_board'
DETAIL_URL = 'https://careers.hdi.group/jobs/product-owner-data-platform'
SEEDED_DETAIL_URL = 'https://job.hdi.group/job/Data-&-Analytics-Engineer-%28Long-Tail%29/720-en_US/'
PRODUCT_URL = 'https://careers.hdi.group/en/about/news/product-data-platform'


def fake_fetcher(url: str) -> tuple[str, str, int]:
    if url == LISTING_URL:
        html = (
            "<html><body>"
            f"<a href='{DETAIL_URL}'>Product Owner Data Platform Hannover</a>"
            "<a href='/jobs/duales-studium-data'>Duales Studium Data Hannover</a>"
            f"<a href='{PRODUCT_URL}'>Product Data Platform News Hannover</a>"
            f"<a href='{PRODUCT_URL}'>Product Data Platform News Hannover</a>"
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

    if url == SEEDED_DETAIL_URL:
        html = (
            "<html>"
            "<title>Data & Analytics Engineer (Long Tail)</title>"
            "<body>Data & Analytics Engineer in Hannover or remote Germany. SQL, Python, Analytics.</body>"
            "</html>"
        )
        return html, SEEDED_DETAIL_URL, 200

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


def test_extract_candidate_links_is_bounded_to_relevant_same_domain_links() -> None:
    html, final_url, _ = fake_fetcher(LISTING_URL)

    candidates = extract_candidate_links(html, final_url)
    selected = select_detail_candidates(candidates, limit=3)

    assert DETAIL_URL in [candidate.url for candidate in selected]
    assert SEEDED_DETAIL_URL in [candidate.url for candidate in selected]


def test_connector_fetches_bounded_relevant_jobs() -> None:
    connector = HdiConnector(listing_url=LISTING_URL, fetcher=fake_fetcher)

    records, final_url = connector.fetch_jobs(
        profile=make_profile(),
        search_term=SearchTerm("Product Owner", id=1),
    )

    assert final_url == LISTING_URL
    assert len(records) >= 1

    record = next(item for item in records if item.source_url == DETAIL_URL)
    assert record.source_name == SOURCE_NAME
    assert record.source_url == DETAIL_URL
    assert record.external_job_id
    assert record.raw_data["source_type"] == SOURCE_TYPE
    assert record.raw_data["source_family"]
    assert record.raw_data["result_card"]["company_name"] == COMPANY_NAME
    assert "Product Owner" in record.raw_data["result_card"]["title"]
    assert record.raw_data["acquisition_boundary"]["browser_automation_used"] is False
    assert record.raw_data["acquisition_boundary"]["raw_html_persisted"] is False



class FakeResponse:
    def __init__(self, content: bytes, encoding: str | None = None, apparent_encoding: str | None = None) -> None:
        self.content = content
        self.encoding = encoding
        self.apparent_encoding = apparent_encoding


def test_decode_response_text_prefers_utf8_over_misleading_declared_encoding() -> None:
    response = FakeResponse(
        "Manager:in Entschädigungsmanagement – Azure Focus".encode("utf-8"),
        encoding="ISO-8859-1",
        apparent_encoding="Windows-1252",
    )

    assert decode_response_text(response) == "Manager:in Entschädigungsmanagement – Azure Focus"


def test_concrete_job_detail_url_rejects_non_job_pages() -> None:
    assert is_concrete_job_detail_url(DETAIL_URL)
    assert not is_concrete_job_detail_url(PRODUCT_URL)



def test_connector_fetches_seeded_known_detail_jobs() -> None:
    def seeded_fetcher(url: str) -> tuple[str, str, int]:
        if url == LISTING_URL:
            return "<html><body>No server-rendered job links here</body></html>", LISTING_URL, 200

        if url == SEEDED_DETAIL_URL:
            html = (
                "<html>"
                "<title>Data & Analytics Engineer (Long Tail)</title>"
                "<body>Data & Analytics Engineer in Hannover or remote Germany. SQL, Python, Analytics.</body>"
                "</html>"
            )
            return html, SEEDED_DETAIL_URL, 200

        raise AssertionError(f"Unexpected URL: {url}")

    connector = HdiConnector(listing_url=LISTING_URL, fetcher=seeded_fetcher)

    records, final_url = connector.fetch_jobs(
        profile=make_profile(),
        search_term=SearchTerm("Data", id=1),
    )

    assert final_url == LISTING_URL
    assert len(records) == 1
    assert records[0].source_name == SOURCE_NAME
    assert records[0].source_url == SEEDED_DETAIL_URL
    assert "Data" in records[0].raw_data["result_card"]["title"]
