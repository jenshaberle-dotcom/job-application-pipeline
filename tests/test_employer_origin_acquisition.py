from __future__ import annotations

from src.connectors.employer_origin_acquisition import (
    acquire_genuine_job_pages,
    explicit_root_delegated_listing_hosts,
    extract_embedded_detail_urls,
    genuine_job_detail_proof,
    looks_like_listing_navigation,
    parse_page,
)


HOSTS = ("jobs.example.invalid",)
ROOT = "https://jobs.example.invalid/careers"
JOB_HOST_ROOT = "https://jobs.example.invalid"
INFO = "https://jobs.example.invalid/about-us"
LISTING = "https://jobs.example.invalid/open-positions"
DETAIL = "https://jobs.example.invalid/jobs/backend-engineer-berlin-12345"
CLASSIFIED_DETAIL = "https://jobs.example.invalid/careers/platform-engineer"
QUERY_DETAIL = "https://jobs.example.invalid/careers?positionId=AB12CD34"
PRIVACY = "https://jobs.example.invalid/privacy-policy"
ATS_LISTING = "https://acme.wd5.myworkdayjobs.com/en-US/acme"
ATS_DETAIL = "https://acme.wd5.myworkdayjobs.com/en-US/acme/job/Berlin/Platform-Engineer_R123"
SOCIAL_JOBS = "https://www.linkedin.com/jobs/acme"


def job_html(title: str = "Backend Engineer Berlin") -> str:
    return (
        f"<html><title>{title}</title><body>"
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"JobPosting","title":"Backend Engineer"}'
        "</script>Apply now. Responsibilities: build distributed services."
        "</body></html>"
    )


def test_acquisition_uses_one_bounded_listing_hop_without_relevance_gate() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return (
                f"<html><title>Careers</title><a href='{PRIVACY}'>Privacy</a>"
                f"<a href='{LISTING}'>Open positions</a></html>",
                ROOT,
                200,
            )
        if url == LISTING:
            return (
                f"<html><title>Open positions</title><a href='{DETAIL}'>Backend Engineer Berlin</a></html>",
                LISTING,
                200,
            )
        if url == DETAIL:
            return job_html(), DETAIL, 200
        raise AssertionError(url)

    jobs, final_url = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=HOSTS,
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert final_url == ROOT
    assert calls == [ROOT, LISTING, DETAIL]
    assert PRIVACY not in calls
    assert len(jobs) == 1
    assert jobs[0].final_url == DETAIL
    assert jobs[0].proof_kind == "jsonld_jobposting"


def test_jobs_hostname_does_not_make_unrelated_path_listing_navigation() -> None:
    assert looks_like_listing_navigation(INFO, "About us") is False
    assert looks_like_listing_navigation(LISTING, "Open positions") is True


def test_jobs_hostname_noise_does_not_exhaust_bounded_listing_budget() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == JOB_HOST_ROOT:
            return (
                "<html><title>Careers</title><body>"
                f"<a href='{INFO}'>About us</a>"
                f"<a href='{LISTING}'>Open positions</a>"
                "</body></html>",
                JOB_HOST_ROOT,
                200,
            )
        if url == LISTING:
            return (
                f"<html><title>Open positions</title><a href='{DETAIL}'>Backend Engineer Berlin</a></html>",
                LISTING,
                200,
            )
        if url == DETAIL:
            return job_html(), DETAIL, 200
        raise AssertionError(url)

    jobs, final_url = acquire_genuine_job_pages(
        listing_url=JOB_HOST_ROOT,
        allowed_hosts=HOSTS,
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert final_url == JOB_HOST_ROOT
    assert calls == [JOB_HOST_ROOT, LISTING, DETAIL]
    assert INFO not in calls
    assert len(jobs) == 1
    assert jobs[0].final_url == DETAIL


def test_existing_classifier_can_promote_role_like_detail_path() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return (
                f"<html><title>Careers</title><a href='{CLASSIFIED_DETAIL}'>Platform Engineer</a></html>",
                ROOT,
                200,
            )
        if url == CLASSIFIED_DETAIL:
            return job_html("Platform Engineer"), CLASSIFIED_DETAIL, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=HOSTS,
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, CLASSIFIED_DETAIL]
    assert len(jobs) == 1
    assert jobs[0].discovery_source == "classified_detail"
    assert jobs[0].proof_kind == "jsonld_jobposting"


def test_existing_query_detail_extractor_can_promote_position_identifier() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return (
                f"<html><title>Careers</title><a href='{QUERY_DETAIL}'>Platform Engineer</a></html>",
                ROOT,
                200,
            )
        if url == QUERY_DETAIL:
            return job_html("Platform Engineer"), QUERY_DETAIL, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=HOSTS,
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, QUERY_DETAIL]
    assert len(jobs) == 1
    assert jobs[0].discovery_source == "query_detail"
    assert jobs[0].proof_kind == "jsonld_jobposting"


def test_explicit_root_jobs_anchor_delegates_one_external_https_host() -> None:
    page = parse_page(
        requested_url=ROOT,
        html=(
            "<html><title>Careers</title><body>"
            f"<a href='{SOCIAL_JOBS}'>Jobs</a>"
            f"<a href='{ATS_LISTING}'>View jobs</a>"
            "</body></html>"
        ),
        final_url=ROOT,
        status_code=200,
    )

    assert explicit_root_delegated_listing_hosts(page, allowed_hosts=HOSTS) == (
        "acme.wd5.myworkdayjobs.com",
    )


def test_acquisition_can_follow_explicit_root_ats_delegation_without_transitive_authority() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return (
                "<html><title>Careers</title><body>"
                f"<a href='{SOCIAL_JOBS}'>Jobs</a>"
                f"<a href='{ATS_LISTING}'>To the jobs</a>"
                "</body></html>",
                ROOT,
                200,
            )
        if url == ATS_LISTING:
            return (
                f"<html><title>Open positions</title><a href='{ATS_DETAIL}'>Platform Engineer</a></html>",
                ATS_LISTING,
                200,
            )
        if url == ATS_DETAIL:
            return job_html("Platform Engineer"), ATS_DETAIL, 200
        raise AssertionError(url)

    jobs, final_url = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=HOSTS,
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert final_url == ROOT
    assert calls == [ROOT, ATS_LISTING, ATS_DETAIL]
    assert SOCIAL_JOBS not in calls
    assert len(jobs) == 1
    assert jobs[0].final_url == ATS_DETAIL
    assert jobs[0].proof_kind == "jsonld_jobposting"


def test_embedded_detail_url_is_discovered_without_anchor() -> None:
    escaped = DETAIL.replace("/", r"\/")
    html = f'<html><script>window.__STATE__={{"jobUrl":"{escaped}"}}</script></html>'

    assert extract_embedded_detail_urls(html, ROOT, allowed_hosts=HOSTS) == (DETAIL,)


def test_genuine_detail_rejects_privacy_even_with_job_words() -> None:
    page = parse_page(
        requested_url=PRIVACY,
        html="<html><title>Privacy Policy</title><body>Apply now job requirements</body></html>",
        final_url=PRIVACY,
        status_code=200,
    )

    assert genuine_job_detail_proof(page, allowed_hosts=HOSTS) is None


def test_job_url_and_content_can_prove_without_jsonld() -> None:
    page = parse_page(
        requested_url=DETAIL,
        html=(
            "<html><title>Backend Engineer Berlin</title><body>"
            "Your responsibilities include building and operating distributed backend services, "
            "reviewing production changes, and improving platform reliability. "
            "Requirements include Python experience, API design, and collaborative engineering. "
            "Apply now."
            "</body></html>"
        ),
        final_url=DETAIL,
        status_code=200,
    )

    assert genuine_job_detail_proof(page, allowed_hosts=HOSTS) == "job_url_and_job_content"
