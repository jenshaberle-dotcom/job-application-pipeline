from __future__ import annotations

from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.successfactors import EON_GERMANY_TARGET
from src.connectors.successfactors_preview import (
    SuccessFactorsPreviewConnector,
    is_concrete_requested_term,
)


LISTING_URL = EON_GERMANY_TARGET.listing_url
DATA_URL = (
    "https://careers.eon.com/deutschland/job/"
    "Essen-%28Senior%29-Data-Engineer-Data-%26-AI-%28fmd%29/1414903533/"
)
ARCHITECT_URL = (
    "https://careers.eon.com/deutschland/job/"
    "Essen-Business-Solution-Architect-Core-Energy-Retail-%28fmd%29/1277690001/"
)


def listing_html() -> str:
    return (
        "<html><body>"
        f"<a href='{DATA_URL}'>(Senior) Data Engineer Data &amp; AI (f/m/d)</a>"
        f"<a href='{ARCHITECT_URL}'>Business Solution Architect Core - Energy Retail (f/m/d)</a>"
        "</body></html>"
    )


def detail_html(title: str) -> str:
    return (
        "<html>"
        f"<title>{title} Job Details | E.ON</title>"
        f"<body><h1>{title}</h1>"
        "E.ON Digital Technology GmbH | Permanent | Full time "
        "The role works with AI, cloud platforms and enterprise data capabilities."
        "</body></html>"
    )


def make_profile() -> SearchProfile:
    return SearchProfile(
        id=-1,
        profile_name="preview_test",
        source_name="successfactors:eon_germany",
        search_location=None,
        search_radius_km=None,
        offer_type=None,
        page_size=5,
    )


def make_fetcher(calls: list[str]):
    def fake_fetcher(url: str) -> tuple[str, str, int]:
        calls.append(url)
        if url == LISTING_URL:
            return listing_html(), LISTING_URL, 200
        if url == DATA_URL:
            return detail_html("(Senior) Data Engineer Data & AI (f/m/d)"), DATA_URL, 200
        if url == ARCHITECT_URL:
            return (
                detail_html("Business Solution Architect Core - Energy Retail (f/m/d)"),
                ARCHITECT_URL,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    return fake_fetcher


def test_concrete_data_term_does_not_fetch_unrelated_profile_role() -> None:
    calls: list[str] = []
    connector = SuccessFactorsPreviewConnector(
        target_key="eon_germany",
        max_detail_pages=5,
        fetcher=make_fetcher(calls),
    )

    records, final_url = connector.fetch_jobs(
        make_profile(),
        SearchTerm(search_term="Data", id=None),
    )

    assert final_url == LISTING_URL
    assert calls == [LISTING_URL, DATA_URL]
    assert [record.source_url for record in records] == [DATA_URL]
    assert records[0].raw_data["listing_evidence"]["requested_term_match"] is True
    assert records[0].raw_data["acquisition_boundary"]["request_count"] == 2


def test_multi_token_requested_term_is_supported() -> None:
    calls: list[str] = []
    connector = SuccessFactorsPreviewConnector(
        target_key="eon_germany",
        max_detail_pages=5,
        fetcher=make_fetcher(calls),
    )

    records, _ = connector.fetch_jobs(
        make_profile(),
        SearchTerm(search_term="Data Engineer", id=None),
    )

    assert calls == [LISTING_URL, DATA_URL]
    assert len(records) == 1
    assert "Data Engineer" in records[0].raw_data["result_card"]["title"]


def test_wildcard_preview_preserves_broad_profile_sampling() -> None:
    calls: list[str] = []
    connector = SuccessFactorsPreviewConnector(
        target_key="eon_germany",
        max_detail_pages=5,
        fetcher=make_fetcher(calls),
    )

    records, _ = connector.fetch_jobs(
        make_profile(),
        SearchTerm(search_term="*", id=None),
    )

    assert calls == [LISTING_URL, DATA_URL, ARCHITECT_URL]
    assert {record.source_url for record in records} == {DATA_URL, ARCHITECT_URL}


def test_only_non_empty_non_wildcard_terms_are_concrete() -> None:
    assert is_concrete_requested_term("Data")
    assert is_concrete_requested_term("Data Engineer")
    assert not is_concrete_requested_term("*")
    assert not is_concrete_requested_term("")
    assert not is_concrete_requested_term("   ")
