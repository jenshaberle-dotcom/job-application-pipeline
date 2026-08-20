from __future__ import annotations

from src.connectors.employer_origin_acquisition import (
    acquire_genuine_job_pages,
    extract_embedded_detail_urls,
    genuine_job_detail_proof,
    looks_like_listing_navigation,
    parse_page,
)


HOSTS = ("jobs.example.test",)
ROOT = "https://jobs.example.test/careers"
JOB_HOST_ROOT = "https://jobs.example.test"
INFO = "https://jobs.example.test/about-us"
LISTING = "https://jobs.example.test/open-positions"
DETAIL = "https://jobs.example.test/jobs/backend-engineer-berlin-12345"
PRIVACY = "https://jobs.example.test/privacy-policy"


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
