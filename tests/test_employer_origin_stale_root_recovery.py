from __future__ import annotations

import requests
import pytest

from src.connectors import employer_origin_acquisition_v4_root_recovery as wrapper
from src.connectors.employer_origin_stale_root_recovery import (
    direct_same_host_parent_url,
    recoverable_root_http_status,
)


STALE = "https://db.jobs/de-de/jobs"
PARENT = "https://db.jobs/de-de"
HOSTS = ("db.jobs",)


def _http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    response.url = STALE
    return requests.HTTPError(f"{status} Client Error for url: {STALE}", response=response)


def test_direct_same_host_parent_is_derived_without_guessing_locale_or_route() -> None:
    assert direct_same_host_parent_url(STALE, allowed_hosts=HOSTS) == PARENT
    assert (
        direct_same_host_parent_url(
            "https://db.jobs/de-de/jobs?lang=de#top",
            allowed_hosts=HOSTS,
        )
        == PARENT
    )


def test_parent_recovery_rejects_shallow_cross_host_and_non_https_inputs() -> None:
    assert direct_same_host_parent_url("https://db.jobs/jobs", allowed_hosts=HOSTS) is None
    assert direct_same_host_parent_url(STALE, allowed_hosts=("jobs.example.invalid",)) is None
    assert direct_same_host_parent_url("http://db.jobs/de-de/jobs", allowed_hosts=HOSTS) is None


def test_only_404_and_410_are_recoverable_root_statuses() -> None:
    assert recoverable_root_http_status(404)
    assert recoverable_root_http_status(410)
    assert not recoverable_root_http_status(403)
    assert not recoverable_root_http_status(500)
    assert not recoverable_root_http_status(None)


def test_wrapper_recovers_one_http_404_root_to_direct_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, object]] = []
    sentinel_executor = object()

    def fake_acquire(**kwargs):
        calls.append((kwargs["listing_url"], kwargs["request_executor"]))
        if kwargs["listing_url"] == STALE:
            raise _http_error(404)
        assert kwargs["listing_url"] == PARENT
        return [], PARENT

    monkeypatch.setattr(wrapper, "_acquire_genuine_job_pages", fake_acquire)

    result = wrapper.acquire_genuine_job_pages(
        listing_url=STALE,
        allowed_hosts=HOSTS,
        known_detail_urls=(),
        fetcher=lambda _url: (_ for _ in ()).throw(AssertionError("unused")),
        request_executor=sentinel_executor,
        max_followup_requests=2,
        max_results=1,
    )

    assert result == ([], PARENT)
    assert calls == [(STALE, sentinel_executor), (PARENT, sentinel_executor)]


def test_wrapper_recovers_explicit_returned_410_root_status(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_acquire(**kwargs):
        calls.append(kwargs["listing_url"])
        if len(calls) == 1:
            raise RuntimeError("listing request failed with status 410")
        return [], kwargs["listing_url"]

    monkeypatch.setattr(wrapper, "_acquire_genuine_job_pages", fake_acquire)

    assert wrapper.acquire_genuine_job_pages(
        listing_url=STALE,
        allowed_hosts=HOSTS,
        known_detail_urls=(),
        fetcher=lambda _url: None,
    ) == ([], PARENT)
    assert calls == [STALE, PARENT]


def test_wrapper_does_not_recover_403_500_timeout_or_contract_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    failures: tuple[BaseException, ...] = (
        _http_error(403),
        _http_error(500),
        requests.Timeout("timed out"),
        RuntimeError("listing source binding mismatch"),
        RuntimeError("listing request failed with status 500"),
    )

    for failure in failures:
        def fake_acquire(**_kwargs):
            raise failure

        monkeypatch.setattr(wrapper, "_acquire_genuine_job_pages", fake_acquire)
        with pytest.raises(type(failure)):
            wrapper.acquire_genuine_job_pages(
                listing_url=STALE,
                allowed_hosts=HOSTS,
                known_detail_urls=(),
                fetcher=lambda _url: None,
            )


def test_wrapper_fails_closed_when_stale_root_has_no_direct_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_acquire(**_kwargs):
        raise _http_error(404)

    monkeypatch.setattr(wrapper, "_acquire_genuine_job_pages", fake_acquire)

    with pytest.raises(RuntimeError, match="no authorized direct-parent recovery"):
        wrapper.acquire_genuine_job_pages(
            listing_url="https://db.jobs/jobs",
            allowed_hosts=HOSTS,
            known_detail_urls=(),
            fetcher=lambda _url: None,
        )
