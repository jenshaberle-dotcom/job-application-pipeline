from __future__ import annotations

import requests
import pytest

from src.connectors import employer_origin_acquisition_v4_root_recovery as wrapper
from src.connectors.employer_origin_acquisition import parse_page
from src.connectors.employer_origin_acquisition_v4_forms import MeteredRequest
from src.connectors.employer_origin_stale_root_recovery import (
    direct_same_host_parent_url,
    recoverable_root_http_status,
    strict_primary_listing_url,
)


STALE = "https://db.jobs/de-de/jobs"
PARENT = "https://db.jobs/de-de"
PRIMARY = "https://db.jobs/service/search/de-de/5379744?qli=true&query="
SECOND_PRIMARY = "https://db.jobs/service/search/de-de/9999999?qli=true&query="
HOSTS = ("db.jobs",)


def _http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    response.url = STALE
    return requests.HTTPError(f"{status} Client Error for url: {STALE}", response=response)


def _parent_html(*, primary: bool = True, second_primary: bool = False) -> str:
    links = ["<a href='/de-de/dein-einstieg/studierende'>Studierende</a>"]
    if primary:
        links.append(f"<a href='{PRIMARY}'>Job board</a>")
    if second_primary:
        links.append(f"<a href='{SECOND_PRIMARY}'>Job search</a>")
    return "<html><title>Karriere</title><body>" + "".join(links) + "</body></html>"


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


def test_recovered_parent_selects_one_explicit_primary_job_board_over_target_group_links() -> None:
    page = parse_page(
        requested_url=PARENT,
        html=_parent_html(),
        final_url=PARENT,
        status_code=200,
    )
    assert strict_primary_listing_url(page, allowed_hosts=HOSTS) == PRIMARY


def test_recovered_parent_primary_listing_is_ambiguous_fail_closed() -> None:
    page = parse_page(
        requested_url=PARENT,
        html=_parent_html(second_primary=True),
        final_url=PARENT,
        status_code=200,
    )
    assert strict_primary_listing_url(page, allowed_hosts=HOSTS) is None


def test_recovered_parent_rejects_cross_host_primary_listing() -> None:
    page = parse_page(
        requested_url=PARENT,
        html="<a href='https://external.invalid/jobs'>Job board</a>",
        final_url=PARENT,
        status_code=200,
    )
    assert strict_primary_listing_url(page, allowed_hosts=HOSTS) is None


def test_wrapper_uses_primary_listing_after_one_404_parent_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    acquire_calls: list[tuple[str, int]] = []
    executor_calls: list[MeteredRequest] = []

    def fake_acquire(**kwargs):
        acquire_calls.append((kwargs["listing_url"], kwargs["max_followup_requests"]))
        if kwargs["listing_url"] == STALE:
            raise _http_error(404)
        assert kwargs["listing_url"] == PRIMARY
        return ["job"], PRIMARY

    def executor(request: MeteredRequest):
        executor_calls.append(request)
        assert request == MeteredRequest(PARENT)
        return _parent_html(), PARENT, 200

    monkeypatch.setattr(wrapper, "_acquire_genuine_job_pages", fake_acquire)

    result = wrapper.acquire_genuine_job_pages(
        listing_url=STALE,
        allowed_hosts=HOSTS,
        known_detail_urls=(),
        fetcher=lambda _url: (_ for _ in ()).throw(AssertionError("unused")),
        request_executor=executor,
        max_followup_requests=2,
        max_results=1,
    )

    assert result == (["job"], PRIMARY)
    assert executor_calls == [MeteredRequest(PARENT)]
    assert acquire_calls == [(STALE, 2), (PRIMARY, 1)]


def test_wrapper_caches_parent_when_no_unique_primary_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    acquire_calls: list[str] = []
    executor_calls: list[MeteredRequest] = []

    def real_executor(request: MeteredRequest):
        executor_calls.append(request)
        assert request == MeteredRequest(PARENT)
        return _parent_html(primary=False), PARENT, 200

    def fake_acquire(**kwargs):
        acquire_calls.append(kwargs["listing_url"])
        if kwargs["listing_url"] == STALE:
            raise _http_error(404)
        assert kwargs["listing_url"] == PARENT
        html, final_url, status = kwargs["request_executor"](MeteredRequest(PARENT))
        assert "Studierende" in html
        assert final_url == PARENT
        assert status == 200
        return [], PARENT

    monkeypatch.setattr(wrapper, "_acquire_genuine_job_pages", fake_acquire)

    assert wrapper.acquire_genuine_job_pages(
        listing_url=STALE,
        allowed_hosts=HOSTS,
        known_detail_urls=(),
        fetcher=lambda _url: (_ for _ in ()).throw(AssertionError("unused")),
        request_executor=real_executor,
        max_followup_requests=2,
    ) == ([], PARENT)
    assert acquire_calls == [STALE, PARENT]
    assert executor_calls == [MeteredRequest(PARENT)]


def test_wrapper_recovers_explicit_returned_410_root_status(monkeypatch: pytest.MonkeyPatch) -> None:
    acquire_calls: list[tuple[str, int]] = []

    def fake_acquire(**kwargs):
        acquire_calls.append((kwargs["listing_url"], kwargs["max_followup_requests"]))
        if kwargs["listing_url"] == STALE:
            raise RuntimeError("listing request failed with status 410")
        return [], kwargs["listing_url"]

    monkeypatch.setattr(wrapper, "_acquire_genuine_job_pages", fake_acquire)

    assert wrapper.acquire_genuine_job_pages(
        listing_url=STALE,
        allowed_hosts=HOSTS,
        known_detail_urls=(),
        fetcher=lambda url: (_parent_html(), url, 200),
    ) == ([], PRIMARY)
    assert acquire_calls == [(STALE, 2), (PRIMARY, 1)]


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
                fetcher=lambda _url: (_ for _ in ()).throw(AssertionError("no parent fetch")),
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


def test_wrapper_does_not_recover_without_followup_capacity(monkeypatch: pytest.MonkeyPatch) -> None:
    failure = _http_error(404)

    def fake_acquire(**_kwargs):
        raise failure

    monkeypatch.setattr(wrapper, "_acquire_genuine_job_pages", fake_acquire)

    with pytest.raises(requests.HTTPError):
        wrapper.acquire_genuine_job_pages(
            listing_url=STALE,
            allowed_hosts=HOSTS,
            known_detail_urls=(),
            fetcher=lambda _url: (_ for _ in ()).throw(AssertionError("no parent fetch")),
            max_followup_requests=0,
        )
