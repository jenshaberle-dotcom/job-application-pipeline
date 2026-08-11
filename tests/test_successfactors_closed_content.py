from __future__ import annotations

from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.successfactors import EON_GERMANY_TARGET, SuccessFactorsConnector


LISTING_URL = EON_GERMANY_TARGET.listing_url
JOB_URL = (
    "https://careers.eon.com/deutschland/job/"
    "Hannover-Data-Engineer-%28mwd%29/1414904555/"
)


def test_explicit_2xx_closed_detail_is_not_emitted_as_positive_record() -> None:
    calls: list[str] = []

    def fake_fetcher(url: str) -> tuple[str, str, int]:
        calls.append(url)
        if url == LISTING_URL:
            return (
                f"<html><body><a href='{JOB_URL}'>Data Engineer (m/w/d)</a></body></html>",
                LISTING_URL,
                200,
            )
        if url == JOB_URL:
            return (
                "<html><title>Data Engineer (m/w/d) Job Details | E.ON</title>"
                "<body><h1>Data Engineer (m/w/d)</h1>"
                "E.ON Digital Technology GmbH | Permanent | Full time "
                "Build data platforms with Python and SQL. "
                "This job is no longer available."
                "</body></html>",
                JOB_URL,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    connector = SuccessFactorsConnector(
        target_key="eon_germany",
        max_detail_pages=1,
        fetcher=fake_fetcher,
    )
    profile = SearchProfile(
        id=-1,
        profile_name="unit_test",
        source_name="successfactors:eon_germany",
        search_location=None,
        search_radius_km=None,
        offer_type=None,
        page_size=10,
    )

    records, final_url = connector.fetch_jobs(
        profile,
        SearchTerm(search_term="*", id=None),
    )

    assert final_url == LISTING_URL
    assert calls == [LISTING_URL, JOB_URL]
    assert records == []
