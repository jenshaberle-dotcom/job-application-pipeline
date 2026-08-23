from __future__ import annotations

import pytest

from src.connectors import employer_origin_acquisition_v4_root_recovery as wrapper


DELOITTE_ROOT = "https://careers.deloitte.com/"
DELOITTE_FINAL = "https://www.deloitte.com/de/de/careers.html"


def test_exact_evidenced_deloitte_root_redirect_is_authorized_without_extra_request() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        assert url == DELOITTE_ROOT
        return "<html><title>Careers</title></html>", DELOITTE_FINAL, 200

    jobs, observed_root = wrapper.acquire_genuine_job_pages(
        listing_url=DELOITTE_ROOT,
        allowed_hosts=("careers.deloitte.com",),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=0,
    )

    assert jobs == []
    assert observed_root == DELOITTE_FINAL
    assert calls == [DELOITTE_ROOT]


def test_unrelated_cross_host_root_redirect_remains_fail_closed() -> None:
    source = "https://careers.example.invalid/"
    redirected = "https://www.example.invalid/careers"

    with pytest.raises(RuntimeError, match="listing source binding mismatch"):
        wrapper.acquire_genuine_job_pages(
            listing_url=source,
            allowed_hosts=("careers.example.invalid",),
            known_detail_urls=(),
            fetcher=lambda url: ("<html></html>", redirected, 200),
            max_followup_requests=0,
        )


def test_deloitte_binding_is_not_added_when_source_host_is_not_authorized() -> None:
    assert wrapper._effective_root_allowed_hosts(
        DELOITTE_ROOT,
        ("jobs.example.invalid",),
    ) == ("jobs.example.invalid",)
