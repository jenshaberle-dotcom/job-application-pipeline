from __future__ import annotations

from src.connectors.employer_origin_acquisition_v4 import acquire_genuine_job_pages


HOST = "jobs.example.invalid"
ROOT = "https://jobs.example.invalid/careers"
LISTING_ONE = "https://jobs.example.invalid/open-positions"
LISTING_TWO = "https://jobs.example.invalid/jobs"
QUERY_DETAIL = "https://jobs.example.invalid/job?vacancieid=2026-114"
PATH_DETAIL = "https://jobs.example.invalid/jobs/backend-engineer-12345"
REQUISITION_LISTING = "https://jobs.example.invalid/stellenmarkt"
REQUISITION_FILTER = "https://jobs.example.invalid/stellenmarkt/?filter[area]=2"
REQUISITION_DETAIL = (
    "https://jobs.example.invalid/stellenmarkt/AI-DevOps-Engineer-mwd-de-j2036.html"
)
PERSONIO_HOST = "x1f.jobs.personio.de"
PERSONIO_ROOT = f"https://{PERSONIO_HOST}/"
PERSONIO_XML = f"https://{PERSONIO_HOST}/xml?language=de"
PERSONIO_DETAIL = f"https://{PERSONIO_HOST}/job/123456?language=de"
EMPLOYER_HOST = "www.example.invalid"
EMPLOYER_ROOT = f"https://{EMPLOYER_HOST}/careers"
EMPLOYER_LISTING = f"https://{EMPLOYER_HOST}/careers/our-offers"
SMART_DETAIL = (
    "https://jobs.smartrecruiters.com/Wavestone1/"
    "744000143599414-junior-ai-engineer-pittsburgh-pa"
)


def _root_with_two_listing_candidates() -> str:
    return (
        "<html><body>"
        f"<a href='{LISTING_ONE}'>Open positions</a>"
        f"<a href='{LISTING_TWO}'>Jobs</a>"
        "</body></html>"
    )


def _job_content(title: str) -> str:
    return (
        f"<html><title>{title}</title><body>"
        "Apply now. Responsibilities, requirements and your profile."
        "</body></html>"
    )


def _jsonld_job_content(title: str) -> str:
    return (
        f"<html><title>{title}</title>"
        "<script type='application/ld+json'>"
        f'{{"@type":"JobPosting","title":"{title}"}}'
        "</script><body>Apply now. Responsibilities and requirements.</body></html>"
    )


def test_personio_provider_inventory_reaches_real_detail_within_bounded_budget() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == PERSONIO_ROOT:
            return "<html><title>Jobs bei X1F</title><body>Jobs</body></html>", PERSONIO_ROOT, 200
        if url == PERSONIO_XML:
            return (
                "<?xml version='1.0' encoding='UTF-8'?><workzag-jobs>"
                "<position><id>123456</id><name>Data Engineer</name></position>"
                "</workzag-jobs>",
                PERSONIO_XML,
                200,
            )
        if url == PERSONIO_DETAIL:
            return (
                "<html><title>Data Engineer</title><script type='application/ld+json'>"
                '{"@type":"JobPosting","title":"Data Engineer"}'
                "</script><body>Apply now</body></html>",
                PERSONIO_DETAIL,
                200,
            )
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=PERSONIO_ROOT,
        allowed_hosts=(PERSONIO_HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [PERSONIO_ROOT, PERSONIO_XML, PERSONIO_DETAIL]
    assert len(jobs) == 1
    assert jobs[0].final_url == PERSONIO_DETAIL
    assert jobs[0].discovery_source == "personio_provider_detail"
    assert jobs[0].proof_kind == "jsonld_jobposting"


def test_explicit_embedded_canonical_ats_detail_reuses_provider_delegation_contract() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == EMPLOYER_ROOT:
            return (
                f"<html><a href='{EMPLOYER_LISTING}'>Our offers</a></html>",
                EMPLOYER_ROOT,
                200,
            )
        if url == EMPLOYER_LISTING:
            return (
                f'<html><script>window.jobs={{"detail":"{SMART_DETAIL}"}}</script></html>',
                EMPLOYER_LISTING,
                200,
            )
        if url == SMART_DETAIL:
            return _jsonld_job_content("Junior AI Engineer"), SMART_DETAIL, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=EMPLOYER_ROOT,
        allowed_hosts=(EMPLOYER_HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [EMPLOYER_ROOT, EMPLOYER_LISTING, SMART_DETAIL]
    assert len(jobs) == 1
    assert jobs[0].final_url == SMART_DETAIL
    assert jobs[0].discovery_source == "smartrecruiters_provider_delegated_detail"
    assert jobs[0].proof_kind == "jsonld_jobposting"


def test_strong_html_requisition_detail_wins_remaining_base_followup() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return (
                f"<html><a href='{REQUISITION_LISTING}'>Stellenmarkt</a></html>",
                ROOT,
                200,
            )
        if url == REQUISITION_LISTING:
            return (
                "<html><body>"
                f"<a href='{REQUISITION_FILTER}'>Consulting</a>"
                f"<a href='{REQUISITION_DETAIL}'>AI DevOps Engineer (m/w/d)</a>"
                "</body></html>",
                REQUISITION_LISTING,
                200,
            )
        if url == REQUISITION_DETAIL:
            return _job_content("AI DevOps Engineer (m/w/d)"), REQUISITION_DETAIL, 200
        if url == REQUISITION_FILTER:
            raise AssertionError("detail candidate must outrank another listing filter")
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, REQUISITION_LISTING, REQUISITION_DETAIL]
    assert len(jobs) == 1
    assert jobs[0].final_url == REQUISITION_DETAIL
    assert jobs[0].discovery_source == "anchor_detail"


def test_trusted_query_detail_at_budget_boundary_gets_single_extra_followup() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return _root_with_two_listing_candidates(), ROOT, 200
        if url == LISTING_ONE:
            return "<html><title>Open positions</title></html>", LISTING_ONE, 200
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
            return _root_with_two_listing_candidates(), ROOT, 200
        if url == LISTING_ONE:
            return "<html><title>Open positions</title></html>", LISTING_ONE, 200
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
