from __future__ import annotations

from src.connectors.employer_origin_acquisition import parse_page
from src.connectors.employer_origin_acquisition_v4_forms import MeteredRequest
from src.connectors.employer_origin_portal_delegation import explicit_bounded_portal_urls
from src.connectors.employer_origin_portal_delegation_acquisition import (
    acquire_via_explicit_portal,
)


EMPLOYER = "https://www.example.com/karriere"
EMPLOYER_HOST = "www.example.com"
PORTAL = "https://karriere.example.com/"
DETAIL = "https://karriere.example.com/jobs/platform-engineer-123"


def _page(html: str):
    return parse_page(
        requested_url=EMPLOYER,
        html=html,
        final_url=EMPLOYER,
        status_code=200,
    )


def test_strong_german_portal_cta_accepts_same_employer_career_host() -> None:
    html = f'<a href="{PORTAL}">Jetzt einen Job finden</a>'
    assert explicit_bounded_portal_urls(
        _page(html),
        allowed_hosts={EMPLOYER_HOST},
    ) == (PORTAL.rstrip("/"),)


def test_strong_portal_cta_rejects_unrelated_noncareer_destination() -> None:
    html = '<a href="https://shop.unrelated.example/">Zum Jobportal</a>'
    assert explicit_bounded_portal_urls(
        _page(html),
        allowed_hosts={EMPLOYER_HOST},
    ) == ()


def test_strong_portal_cta_rejects_social_destination() -> None:
    html = '<a href="https://www.linkedin.com/company/example/jobs/">Job finden</a>'
    assert explicit_bounded_portal_urls(
        _page(html),
        allowed_hosts={EMPLOYER_HOST},
    ) == ()


def test_weak_generic_link_does_not_expand_delegation() -> None:
    html = f'<a href="{PORTAL}">Mehr erfahren</a>'
    assert explicit_bounded_portal_urls(
        _page(html),
        allowed_hosts={EMPLOYER_HOST},
    ) == ()


def test_portal_bridge_reaches_strict_detail_without_global_marker_widening() -> None:
    calls: list[MeteredRequest] = []

    employer_html = f'<a href="{PORTAL}">Zum Jobportal</a>'
    portal_html = f'<a href="{DETAIL}">Platform Engineer</a>'
    detail_html = """
        <html>
          <head><title>Platform Engineer</title></head>
          <body>
            <h1>Platform Engineer</h1>
            <h2>Your responsibilities</h2>
            <p>Build reliable platform services and production systems.</p>
            <h2>Requirements</h2>
            <p>Experience with distributed systems, observability, and automation.</p>
          </body>
        </html>
    """

    def execute(request: MeteredRequest) -> tuple[str, str, int]:
        calls.append(request)
        assert request.method == "GET"
        assert not request.fields
        if request.url == EMPLOYER:
            return employer_html, EMPLOYER, 200
        if request.url == PORTAL.rstrip("/"):
            return portal_html, PORTAL, 200
        if request.url == DETAIL:
            return detail_html, DETAIL, 200
        raise AssertionError(f"unexpected request: {request}")

    jobs, observed_portal = acquire_via_explicit_portal(
        listing_url=EMPLOYER,
        allowed_hosts=(EMPLOYER_HOST,),
        known_detail_urls=(),
        fetcher=lambda _url: (_ for _ in ()).throw(AssertionError("fetcher should not be used")),
        request_executor=execute,
        max_followup_requests=2,
        max_results=1,
    )

    assert observed_portal == PORTAL
    assert len(jobs) == 1
    assert jobs[0].final_url == DETAIL
    assert jobs[0].proof_kind == "job_url_and_job_content"
    assert [item.url for item in calls] == [EMPLOYER, PORTAL.rstrip("/"), DETAIL]


def test_portal_bridge_fails_closed_when_two_strong_portals_are_present() -> None:
    calls: list[MeteredRequest] = []
    root_html = (
        f'<a href="{PORTAL}">Job finden</a>'
        '<a href="https://jobs.example.com/">Zum Jobportal</a>'
    )

    def execute(request: MeteredRequest) -> tuple[str, str, int]:
        calls.append(request)
        if request.url == EMPLOYER:
            return root_html, EMPLOYER, 200
        raise AssertionError("ambiguous portal evidence must stop after employer root")

    jobs, observed = acquire_via_explicit_portal(
        listing_url=EMPLOYER,
        allowed_hosts=(EMPLOYER_HOST,),
        known_detail_urls=(),
        fetcher=lambda _url: (_ for _ in ()).throw(AssertionError("fetcher should not be used")),
        request_executor=execute,
    )

    assert jobs == []
    assert observed == EMPLOYER
    assert [item.url for item in calls] == [EMPLOYER]
