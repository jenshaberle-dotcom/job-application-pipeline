from __future__ import annotations

from src.connectors.employer_origin_acquisition_v4 import acquire_genuine_job_pages


EMPLOYER_HOST = "www.example.invalid"
EMPLOYER_ROOT = "https://www.example.invalid/careers"
ATS_HOST = "jobs.example.invalid"
ATS_ROOT = "https://jobs.example.invalid"
ATS_COUNTRY = "https://jobs.example.invalid/go/germany/4411601"
ATS_DETAIL = "https://jobs.example.invalid/job/Stuttgart-Platform-Engineer/1386287833"
SCAM = "https://www.example.invalid/career/scam-information"
GENERIC_LISTING = "https://www.example.invalid/open-positions"
GENERIC_DETAIL = "https://www.example.invalid/jobs/backend-engineer-12345"


def job_html(title: str = "Platform Engineer") -> str:
    return (
        f"<html><title>{title}</title><body>"
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"JobPosting","title":"Platform Engineer"}'
        "</script>Apply now. Responsibilities and requirements."
        "</body></html>"
    )


def successfactors_root_html() -> str:
    return (
        "<html><title>Career Site</title><body>"
        '<a href="https://career5.successfactors.eu/career?company=acme">Sign in</a>'
        f'<a href="{ATS_COUNTRY}/">Germany</a>'
        "</body></html>"
    )


def test_non_ats_navigation_keeps_original_three_request_budget() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == EMPLOYER_ROOT:
            return (
                f"<html><a href='{GENERIC_LISTING}'>Open positions</a></html>",
                EMPLOYER_ROOT,
                200,
            )
        if url == GENERIC_LISTING:
            return (
                f"<html><a href='{GENERIC_DETAIL}'>Backend Engineer</a></html>",
                GENERIC_LISTING,
                200,
            )
        if url == GENERIC_DETAIL:
            return job_html("Backend Engineer"), GENERIC_DETAIL, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=EMPLOYER_ROOT,
        allowed_hosts=(EMPLOYER_HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [EMPLOYER_ROOT, GENERIC_LISTING, GENERIC_DETAIL]
    assert len(jobs) == 1


def test_successfactors_branded_host_gets_exactly_one_provider_listing_hop() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == EMPLOYER_ROOT:
            return (
                "<html><title>Careers</title><body>"
                f"<a href='{SCAM}'>Scam information</a>"
                f"<a href='{ATS_ROOT}'>View jobs</a>"
                "</body></html>",
                EMPLOYER_ROOT,
                200,
            )
        if url == ATS_ROOT:
            return successfactors_root_html(), ATS_ROOT, 200
        if url == ATS_COUNTRY:
            return (
                f"<html><title>Germany jobs</title><a href='{ATS_DETAIL}'>Platform Engineer</a></html>",
                ATS_COUNTRY,
                200,
            )
        if url == ATS_DETAIL:
            return job_html(), ATS_DETAIL, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=EMPLOYER_ROOT,
        allowed_hosts=(EMPLOYER_HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [EMPLOYER_ROOT, ATS_ROOT, ATS_COUNTRY, ATS_DETAIL]
    assert SCAM not in calls
    assert len(jobs) == 1
    assert jobs[0].final_url == ATS_DETAIL
    assert jobs[0].discovery_source == "anchor_detail"
    assert jobs[0].proof_kind == "jsonld_jobposting"


def test_unrecognized_delegated_host_does_not_receive_fourth_request() -> None:
    calls: list[str] = []
    delegated = "https://recruiting.example.invalid"
    deeper_listing = "https://recruiting.example.invalid/open-positions"
    detail = "https://recruiting.example.invalid/jobs/platform-engineer-12345"

    def fetcher(url: str):
        calls.append(url)
        if url == EMPLOYER_ROOT:
            return f"<html><a href='{delegated}'>View jobs</a></html>", EMPLOYER_ROOT, 200
        if url == delegated:
            return f"<html><a href='{deeper_listing}'>Open positions</a></html>", delegated, 200
        if url == deeper_listing:
            return f"<html><a href='{detail}'>Platform Engineer</a></html>", deeper_listing, 200
        if url == detail:
            return job_html(), detail, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=EMPLOYER_ROOT,
        allowed_hosts=(EMPLOYER_HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [EMPLOYER_ROOT, delegated]
    assert jobs == []


def test_successfactors_extra_grant_is_not_transitive_across_multiple_go_routes() -> None:
    calls: list[str] = []
    second_country = "https://jobs.example.invalid/go/belgium/4411501"

    def fetcher(url: str):
        calls.append(url)
        if url == EMPLOYER_ROOT:
            return f"<html><a href='{ATS_ROOT}'>View jobs</a></html>", EMPLOYER_ROOT, 200
        if url == ATS_ROOT:
            return (
                successfactors_root_html().replace(
                    "</body>", f"<a href='{second_country}/'>Belgium</a></body>"
                ),
                ATS_ROOT,
                200,
            )
        if url == ATS_COUNTRY:
            return "<html><title>Germany jobs</title></html>", ATS_COUNTRY, 200
        if url == second_country:
            return "<html><title>Belgium jobs</title></html>", second_country, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=EMPLOYER_ROOT,
        allowed_hosts=(EMPLOYER_HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert jobs == []
    assert len(calls) == 4
    assert calls[:2] == [EMPLOYER_ROOT, ATS_ROOT]
