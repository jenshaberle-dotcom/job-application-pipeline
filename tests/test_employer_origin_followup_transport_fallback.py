from __future__ import annotations

import pytest
import requests

from src.connectors.employer_origin_acquisition_v4_forms import (
    MeteredRequest,
    acquire_genuine_job_pages,
)


ROOT = "https://jobs.example.invalid/careers"
HOST = "jobs.example.invalid"
STALE = "https://jobs.example.invalid/job/stale-12345"
VALID = "https://jobs.example.invalid/job/platform-engineer-67890"


def _job_html() -> str:
    return (
        "<html><title>Platform Engineer</title><body>"
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"JobPosting","title":"Platform Engineer"}'
        "</script>Apply now. Responsibilities and requirements for this role."
        "</body></html>"
    )


def test_followup_http_failure_consumes_budget_but_does_not_preempt_next_candidate() -> None:
    calls: list[MeteredRequest] = []

    def executor(request: MeteredRequest):
        calls.append(request)
        if request == MeteredRequest(ROOT):
            return "<html><title>Jobs</title></html>", ROOT, 200
        if request == MeteredRequest(STALE):
            raise requests.HTTPError("404 stale vacancy")
        if request == MeteredRequest(VALID):
            return _job_html(), VALID, 200
        raise AssertionError(request)

    jobs, observed_root = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(STALE, VALID),
        fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)),
        request_executor=executor,
        max_followup_requests=2,
    )

    assert observed_root == ROOT
    assert calls == [MeteredRequest(ROOT), MeteredRequest(STALE), MeteredRequest(VALID)]
    assert len(jobs) == 1
    assert jobs[0].final_url == VALID
    assert jobs[0].proof_kind == "jsonld_jobposting"


def test_followup_returned_http_error_status_is_nonfatal_without_retry() -> None:
    calls: list[MeteredRequest] = []

    def executor(request: MeteredRequest):
        calls.append(request)
        if request == MeteredRequest(ROOT):
            return "<html><title>Jobs</title></html>", ROOT, 200
        if request == MeteredRequest(STALE):
            return "not found", STALE, 404
        if request == MeteredRequest(VALID):
            return _job_html(), VALID, 200
        raise AssertionError(request)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(STALE, VALID),
        fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)),
        request_executor=executor,
        max_followup_requests=2,
    )

    assert calls == [MeteredRequest(ROOT), MeteredRequest(STALE), MeteredRequest(VALID)]
    assert len(jobs) == 1
    assert jobs[0].final_url == VALID


def test_root_http_failure_remains_fatal() -> None:
    def executor(request: MeteredRequest):
        assert request == MeteredRequest(ROOT)
        raise requests.HTTPError("404 root")

    with pytest.raises(requests.HTTPError, match="404 root"):
        acquire_genuine_job_pages(
            listing_url=ROOT,
            allowed_hosts=(HOST,),
            known_detail_urls=(),
            fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)),
            request_executor=executor,
            max_followup_requests=2,
        )


def test_non_transport_followup_failure_still_fails_closed() -> None:
    def executor(request: MeteredRequest):
        if request == MeteredRequest(ROOT):
            return "<html><title>Jobs</title></html>", ROOT, 200
        if request == MeteredRequest(STALE):
            raise RuntimeError("contract bug")
        raise AssertionError(request)

    with pytest.raises(RuntimeError, match="contract bug"):
        acquire_genuine_job_pages(
            listing_url=ROOT,
            allowed_hosts=(HOST,),
            known_detail_urls=(STALE,),
            fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)),
            request_executor=executor,
            max_followup_requests=2,
        )
