from __future__ import annotations

from src.connectors.employer_origin_acquisition_v4 import acquire_genuine_job_pages


HOST = "careers.example.invalid"
ROOT = f"https://{HOST}/"
API = f"https://{HOST}/api/jobs"
DETAIL = f"https://{HOST}/jobs/platform-engineer-12345"


def job_html(title: str = "Platform Engineer") -> str:
    return (
        f"<html><title>{title}</title><body>"
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"JobPosting","title":"Platform Engineer"}'
        "</script>Apply now. Responsibilities and requirements."
        "</body></html>"
    )


def test_dynamic_same_host_api_route_reaches_strict_job_detail() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return "<script>const jobs='/api/jobs';</script>", ROOT, 200
        if url == API:
            return '{"jobUrl":"/jobs/platform-engineer-12345"}', API, 200
        if url == DETAIL:
            return job_html(), DETAIL, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, API, DETAIL]
    assert len(jobs) == 1
    assert jobs[0].final_url == DETAIL
    assert jobs[0].discovery_source == "dynamic_route_detail"
    assert jobs[0].proof_kind == "jsonld_jobposting"


def test_dynamic_listing_route_uses_only_shared_fourth_request_grant() -> None:
    listing = f"https://{HOST}/open-positions"
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return f"<a href='{listing}'>Open positions</a>", ROOT, 200
        if url == listing:
            return "<script>const jobs='/api/jobs';</script>", listing, 200
        if url == API:
            return '{"jobUrl":"/jobs/platform-engineer-12345"}', API, 200
        if url == DETAIL:
            return job_html(), DETAIL, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, listing, API, DETAIL]
    assert len(jobs) == 1
    assert jobs[0].discovery_source == "dynamic_route_detail"


def test_dynamic_route_evidence_alone_never_proves_a_job() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return "<script>const jobs='/api/jobs';</script>", ROOT, 200
        if url == API:
            return '{"jobUrl":"/jobs/platform-engineer-12345"}', API, 200
        if url == DETAIL:
            return "<html><title>Careers</title><body>Company overview</body></html>", DETAIL, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, API, DETAIL]
    assert jobs == []


def test_dynamic_delegated_job_host_requires_strong_route_and_strict_page_proof() -> None:
    delegated = "https://jobs.partner.invalid/jobs/platform-engineer-12345"
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return f"<script>const detail='{delegated}';</script>", ROOT, 200
        if url == delegated:
            return job_html(), delegated, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, delegated]
    assert len(jobs) == 1
    assert jobs[0].final_url == delegated
    assert jobs[0].discovery_source.startswith("dynamic_route_delegated_detail:")
    assert jobs[0].proof_kind == "jsonld_jobposting"


def test_dynamic_untrusted_external_host_is_not_fetched() -> None:
    external = "https://apply.partner.invalid/jobs/platform-engineer-12345"
    same_host_fallback = f"https://{HOST}/jobs/platform-engineer-12345"
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return f"<script>const detail='{external}';</script>", ROOT, 200
        if url == same_host_fallback:
            return (
                "<html><title>Careers</title><body>Company overview</body></html>",
                same_host_fallback,
                200,
            )
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert external not in calls
    assert calls == [ROOT, same_host_fallback]
    assert jobs == []



def test_dynamic_delegated_detail_accepts_same_namespace_strong_redirect() -> None:
    requested = "https://career-de-example.icims.invalid/jobs/4425/job"
    final = "https://career-eu-example.icims.invalid/jobs/4425/job"
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return f"<script>const detail='{requested}';</script>", ROOT, 200
        if url == requested:
            return job_html(), final, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, requested]
    assert len(jobs) == 1
    assert jobs[0].final_url == final
    assert jobs[0].proof_kind == "jsonld_jobposting"


def test_dynamic_delegated_detail_rejects_cross_namespace_redirect() -> None:
    requested = "https://career-de-example.icims.invalid/jobs/4425/job"
    final = "https://career-evil.other.invalid/jobs/4425/job"

    def fetcher(url: str):
        if url == ROOT:
            return f"<script>const detail='{requested}';</script>", ROOT, 200
        if url == requested:
            return job_html(), final, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert jobs == []


def test_dynamic_jobposting_apply_route_prefers_strict_parent_detail() -> None:
    listing = f"https://{HOST}/stellenangebote"
    apply_url = "https://karriere.example.invalid/de/jobposting/abcdef1234567890/apply"
    detail = "https://karriere.example.invalid/de/jobposting/abcdef1234567890"
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return f"<a href='{listing}'>Stellenangebote</a>", ROOT, 200
        if url == listing:
            return f"<script>const apply='{apply_url}';</script>", listing, 200
        if url == detail:
            return (
                "<html><title>Platform Engineer</title><body>"
                "Apply now. Responsibilities and requirements. This role owns platform delivery, system reliability, engineering collaboration, implementation, documentation, and operational support."
                "</body></html>",
                detail,
                200,
            )
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, listing, detail]
    assert len(jobs) == 1
    assert jobs[0].final_url == detail
    assert jobs[0].proof_kind == "job_url_and_job_content"
