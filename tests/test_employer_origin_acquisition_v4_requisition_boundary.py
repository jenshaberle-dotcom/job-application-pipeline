from __future__ import annotations

from src.connectors.employer_origin_acquisition_v4 import acquire_genuine_job_pages


HOST = "karriere.example.invalid"
ROOT = f"https://{HOST}/careers"
LISTING_ONE = f"https://{HOST}/open-positions"
LISTING_TWO = f"https://{HOST}/stellenmarkt"
DETAIL = f"https://{HOST}/stellenmarkt/AI-DevOps-Engineer-mwd-de-j2036.html"
GENERIC_DETAIL = f"https://{HOST}/jobs/backend-engineer-12345"


def _job_content() -> str:
    return (
        "<html><title>AI DevOps Engineer (m/w/d)</title><body>"
        "Apply now. Responsibilities, requirements and your profile."
        "</body></html>"
    )


def _root() -> str:
    return (
        "<html><body>"
        f"<a href='{LISTING_ONE}'>Open positions</a>"
        f"<a href='{LISTING_TWO}'>Stellenmarkt</a>"
        "</body></html>"
    )


def test_strong_same_host_requisition_anchor_gets_existing_fourth_request() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return _root(), ROOT, 200
        if url == LISTING_ONE:
            return "<html><title>Open positions</title></html>", LISTING_ONE, 200
        if url == LISTING_TWO:
            return (
                f"<html><a href='{DETAIL}'>AI DevOps Engineer (m/w/d)</a></html>",
                LISTING_TWO,
                200,
            )
        if url == DETAIL:
            return _job_content(), DETAIL, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, LISTING_ONE, LISTING_TWO, DETAIL]
    assert len(jobs) == 1
    assert jobs[0].final_url == DETAIL
    assert jobs[0].discovery_source == "anchor_detail"
    assert jobs[0].proof_kind == "job_url_and_job_content"


def test_generic_path_detail_still_does_not_get_boundary_request() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return _root(), ROOT, 200
        if url == LISTING_ONE:
            return "<html><title>Open positions</title></html>", LISTING_ONE, 200
        if url == LISTING_TWO:
            return (
                f"<html><a href='{GENERIC_DETAIL}'>Backend Engineer</a></html>",
                LISTING_TWO,
                200,
            )
        if url == GENERIC_DETAIL:
            raise AssertionError("generic detail path must not receive the boundary request")
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, LISTING_ONE, LISTING_TWO]
    assert jobs == []
