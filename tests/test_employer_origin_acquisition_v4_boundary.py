from __future__ import annotations

from src.connectors.employer_origin_acquisition_v4 import acquire_genuine_job_pages


HOST = "jobs.example.invalid"
ROOT = "https://jobs.example.invalid/careers"
LISTING_ONE = "https://jobs.example.invalid/open-positions"
LISTING_TWO = "https://jobs.example.invalid/jobs"
QUERY_DETAIL = "https://jobs.example.invalid/job?vacancieid=2026-114"
PATH_DETAIL = "https://jobs.example.invalid/jobs/backend-engineer-12345"


def _job_content(title: str) -> str:
    return (
        f"<html><title>{title}</title><body>"
        "Apply now. Responsibilities, requirements and your profile."
        "</body></html>"
    )


def test_trusted_query_detail_at_budget_boundary_gets_single_extra_followup() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return f"<html><a href='{LISTING_ONE}'>Open positions</a></html>", ROOT, 200
        if url == LISTING_ONE:
            return f"<html><a href='{LISTING_TWO}'>Jobs</a></html>", LISTING_ONE, 200
        if url == LISTING_TWO:
            return (
                f"<html><a href='{QUERY_DETAIL}'>DevOps Engineer (m/w/d)</a></html>",
                LISTING_TWO,
                200,
            )
        if url == QUERY_DETAIL:
            return _job_content("DevOps Engineer (m/w/d)"), QUERY_DETAIL, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, LISTING_ONE, LISTING_TWO, QUERY_DETAIL]
    assert len(jobs) == 1
    assert jobs[0].final_url == QUERY_DETAIL
    assert jobs[0].discovery_source == "query_detail"
    assert jobs[0].proof_kind == "known_detail_and_job_content"


def test_path_detail_at_budget_boundary_does_not_widen_extra_grant() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return f"<html><a href='{LISTING_ONE}'>Open positions</a></html>", ROOT, 200
        if url == LISTING_ONE:
            return f"<html><a href='{LISTING_TWO}'>Jobs</a></html>", LISTING_ONE, 200
        if url == LISTING_TWO:
            return (
                f"<html><a href='{PATH_DETAIL}'>Backend Engineer</a></html>",
                LISTING_TWO,
                200,
            )
        if url == PATH_DETAIL:
            raise AssertionError("path-shaped detail must not receive the boundary request")
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
