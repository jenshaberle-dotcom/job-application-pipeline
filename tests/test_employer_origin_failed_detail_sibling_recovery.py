from __future__ import annotations

import requests

from src.connectors.employer_origin_acquisition_v4_forms import MeteredRequest
from src.connectors.employer_origin_acquisition_v4_root_recovery import (
    acquire_genuine_job_pages,
)


ROOT = "https://jobs.example.invalid/careers"
HOST = "jobs.example.invalid"
STALE = "https://jobs.example.invalid/job/stale-12345"
VALID = "https://jobs.example.invalid/job/platform-engineer-67890"
OTHER = "https://other.example.invalid/job/platform-engineer-67890"


def _root_html(*urls: str) -> str:
    links = "".join(f'<a href="{url}">Job</a>' for url in urls)
    return f"<html><title>Jobs</title><body>{links}</body></html>"


def _job_html() -> str:
    return (
        "<html><title>Platform Engineer</title><body>"
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"JobPosting","title":"Platform Engineer"}'
        "</script>Apply now. Responsibilities and requirements for this role."
        "</body></html>"
    )


def test_failed_detail_uses_unused_bounded_hop_for_already_discovered_same_host_sibling() -> None:
    calls: list[MeteredRequest] = []

    def executor(request: MeteredRequest):
        calls.append(request)
        if request == MeteredRequest(ROOT):
            return _root_html(STALE, VALID), ROOT, 200
        if request == MeteredRequest(STALE):
            raise requests.HTTPError("500 stale detail")
        if request == MeteredRequest(VALID):
            return _job_html(), VALID, 200
        raise AssertionError(request)

    jobs, observed_root = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)),
        request_executor=executor,
        max_followup_requests=1,
    )

    assert observed_root == ROOT
    assert calls == [MeteredRequest(ROOT), MeteredRequest(STALE), MeteredRequest(VALID)]
    assert len(jobs) == 1
    assert jobs[0].final_url == VALID
    assert jobs[0].proof_kind == "jsonld_jobposting"
    assert jobs[0].discovery_source == "anchor_detail_sibling_after_failed_detail"


def test_failed_detail_sibling_recovery_does_not_cross_hosts() -> None:
    calls: list[MeteredRequest] = []

    def executor(request: MeteredRequest):
        calls.append(request)
        if request == MeteredRequest(ROOT):
            return _root_html(STALE, OTHER), ROOT, 200
        if request == MeteredRequest(STALE):
            return "server error", STALE, 500
        if request == MeteredRequest(OTHER):
            raise AssertionError("cross-host sibling must not be attempted")
        raise AssertionError(request)

    jobs, observed_root = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST, "other.example.invalid"),
        known_detail_urls=(),
        fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)),
        request_executor=executor,
        max_followup_requests=1,
    )

    assert observed_root == ROOT
    assert jobs == []
    assert calls == [MeteredRequest(ROOT), MeteredRequest(STALE)]
