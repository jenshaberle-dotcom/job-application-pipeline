from __future__ import annotations

from src.connectors.employer_origin_acquisition_v4_forms import acquire_genuine_job_pages


HOST = "jobs.example.invalid"
ROOT = "https://jobs.example.invalid/careers"
FIRST_LISTING = "https://jobs.example.invalid/open-positions"
SECOND_LISTING = "https://jobs.example.invalid/open-positions/all"
STRONG_DETAIL = "https://jobs.example.invalid/stellenmarkt/platform-engineer-998877.html"
WEAK_DETAIL = "https://jobs.example.invalid/jobs/platform-engineer-12345"


def _job_html() -> str:
    return (
        "<html><title>Platform Engineer</title><body>"
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"JobPosting","title":"Platform Engineer"}'
        "</script>Apply now. Responsibilities and requirements."
        "</body></html>"
    )


def test_form_lane_reuses_strong_requisition_boundary_for_fourth_request() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return f"<html><a href='{FIRST_LISTING}'>Open positions</a></html>", ROOT, 200
        if url == FIRST_LISTING:
            return (
                f"<html><a href='{SECOND_LISTING}'>Open positions</a></html>",
                FIRST_LISTING,
                200,
            )
        if url == SECOND_LISTING:
            return (
                f"<html><a href='{STRONG_DETAIL}'>Platform Engineer (m/w/d)</a></html>",
                SECOND_LISTING,
                200,
            )
        if url == STRONG_DETAIL:
            return _job_html(), STRONG_DETAIL, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, FIRST_LISTING, SECOND_LISTING, STRONG_DETAIL]
    assert len(jobs) == 1
    assert jobs[0].final_url == STRONG_DETAIL
    assert jobs[0].discovery_source == "anchor_detail"
    assert jobs[0].proof_kind == "jsonld_jobposting"


def test_form_lane_does_not_grant_fourth_request_for_non_requisition_detail() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return f"<html><a href='{FIRST_LISTING}'>Open positions</a></html>", ROOT, 200
        if url == FIRST_LISTING:
            return (
                f"<html><a href='{SECOND_LISTING}'>Open positions</a></html>",
                FIRST_LISTING,
                200,
            )
        if url == SECOND_LISTING:
            return (
                f"<html><a href='{WEAK_DETAIL}'>Platform Engineer (m/w/d)</a></html>",
                SECOND_LISTING,
                200,
            )
        if url == WEAK_DETAIL:
            raise AssertionError("non-requisition detail must not receive the shared fourth request")
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, FIRST_LISTING, SECOND_LISTING]
    assert jobs == []
