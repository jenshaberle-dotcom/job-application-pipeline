"""Bounded stale-root recovery around the canonical V4 acquisition helper.

This wrapper adds exactly one recovery opportunity for an employer listing URL
that is proven stale by HTTP 404/410. The recovery target is not guessed: it is
the direct same-host path parent derived from the configured listing URL. The
recovered parent may then nominate exactly one explicit high-confidence job-board
link before control returns to the unchanged V4 acquisition helper.

The caller's metered request executor is shared throughout, so Runtime's absolute
request cap remains authoritative. No retry budget or provider authority is
created here.
"""

from __future__ import annotations

import re

import requests

from src.connectors.employer_origin_acquisition import allowed_host, canonical_url, parse_page
from src.connectors.employer_origin_acquisition_v4_forms import (
    MeteredRequest,
    acquire_genuine_job_pages as _acquire_genuine_job_pages,
)
from src.connectors.employer_origin_stale_root_recovery import (
    direct_same_host_parent_url,
    recoverable_root_http_status,
    strict_primary_listing_url,
)


_RETURNED_ROOT_STATUS = re.compile(r"^listing request failed with status ([0-9]{3})$")


def _recoverable_http_exception(exc: requests.HTTPError) -> bool:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if recoverable_root_http_status(status_code):
        return True
    match = re.search(r"\b(404|410)\b", str(exc))
    return bool(match and recoverable_root_http_status(int(match.group(1))))


def _recoverable_returned_status(exc: RuntimeError) -> bool:
    match = _RETURNED_ROOT_STATUS.fullmatch(str(exc))
    return bool(match and recoverable_root_http_status(int(match.group(1))))


def _fetch_parent(*, parent_url: str, fetcher, request_executor):
    if request_executor is not None:
        return request_executor(MeteredRequest(parent_url))
    return fetcher(parent_url)


def acquire_genuine_job_pages(
    *,
    listing_url: str,
    allowed_hosts: tuple[str, ...],
    known_detail_urls: tuple[str, ...],
    fetcher,
    request_executor=None,
    max_followup_requests: int = 2,
    max_results: int = 1,
):
    """Run canonical V4 acquisition, recovering one stale 404/410 root at most.

    A recovered parent is fetched exactly once. If it exposes exactly one explicit
    high-confidence job-board link, that URL becomes the new V4 root and the local
    follow-up budget is reduced by one because the parent fetch already consumed
    a metered request. This makes the intended stale-root -> parent -> listing ->
    detail route fit Runtime's existing four-request ceiling without widening it.

    If the parent has no unique primary listing link, the unchanged V4 helper runs
    from the already-fetched parent through a one-shot cache so the parent request
    is not counted twice. Any local extra-grant attempt beyond Runtime's global cap
    still fails closed in the existing bounded request executor.
    """

    try:
        return _acquire_genuine_job_pages(
            listing_url=listing_url,
            allowed_hosts=allowed_hosts,
            known_detail_urls=known_detail_urls,
            fetcher=fetcher,
            request_executor=request_executor,
            max_followup_requests=max_followup_requests,
            max_results=max_results,
        )
    except requests.HTTPError as exc:
        if not _recoverable_http_exception(exc):
            raise
        original_error: BaseException = exc
    except RuntimeError as exc:
        if not _recoverable_returned_status(exc):
            raise
        original_error = exc

    if max_followup_requests < 1:
        raise original_error

    parent_url = direct_same_host_parent_url(listing_url, allowed_hosts=allowed_hosts)
    if not parent_url:
        raise RuntimeError("stale listing root has no authorized direct-parent recovery")

    parent_html, parent_final_url, parent_status = _fetch_parent(
        parent_url=parent_url,
        fetcher=fetcher,
        request_executor=request_executor,
    )
    parent_page = parse_page(
        requested_url=parent_url,
        html=str(parent_html),
        final_url=str(parent_final_url),
        status_code=int(parent_status),
    )
    if parent_page.status_code >= 400:
        raise RuntimeError(f"stale listing parent request failed with status {parent_page.status_code}")
    if not allowed_host(parent_page.final_url, allowed_hosts):
        raise RuntimeError("stale listing parent source binding mismatch")

    primary_listing = strict_primary_listing_url(parent_page, allowed_hosts=allowed_hosts)
    if primary_listing:
        return _acquire_genuine_job_pages(
            listing_url=primary_listing,
            allowed_hosts=allowed_hosts,
            known_detail_urls=known_detail_urls,
            fetcher=fetcher,
            request_executor=request_executor,
            max_followup_requests=max(0, max_followup_requests - 1),
            max_results=max_results,
        )

    cache_key = canonical_url(parent_url)
    cache_used = False

    if request_executor is not None:
        def cached_executor(request: MeteredRequest):
            nonlocal cache_used
            request_key = canonical_url(request.url)
            if (
                not cache_used
                and request.method.upper() == "GET"
                and not request.fields
                and request_key == cache_key
            ):
                cache_used = True
                return parent_html, parent_final_url, parent_status
            return request_executor(request)

        return _acquire_genuine_job_pages(
            listing_url=parent_url,
            allowed_hosts=allowed_hosts,
            known_detail_urls=known_detail_urls,
            fetcher=fetcher,
            request_executor=cached_executor,
            max_followup_requests=max_followup_requests,
            max_results=max_results,
        )

    def cached_fetcher(url: str):
        nonlocal cache_used
        if not cache_used and canonical_url(url) == cache_key:
            cache_used = True
            return parent_html, parent_final_url, parent_status
        return fetcher(url)

    return _acquire_genuine_job_pages(
        listing_url=parent_url,
        allowed_hosts=allowed_hosts,
        known_detail_urls=known_detail_urls,
        fetcher=cached_fetcher,
        request_executor=None,
        max_followup_requests=max_followup_requests,
        max_results=max_results,
    )


__all__ = ["acquire_genuine_job_pages"]
