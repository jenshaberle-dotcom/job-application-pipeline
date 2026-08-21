"""Bounded stale-root recovery around the canonical V4 acquisition helper.

This wrapper adds exactly one recovery opportunity for an employer listing URL
that is proven stale by HTTP 404/410. The recovery target is not guessed: it is
the direct same-host path parent derived from the configured listing URL. From
that page onward the unchanged V4 acquisition helper remains the only navigation
and genuine-job authority.

The caller's metered request executor is shared across both attempts, so Runtime's
absolute request cap remains authoritative. No retry budget or provider authority
is created here.
"""

from __future__ import annotations

import re

import requests

from src.connectors.employer_origin_acquisition_v4_forms import (
    acquire_genuine_job_pages as _acquire_genuine_job_pages,
)
from src.connectors.employer_origin_stale_root_recovery import (
    direct_same_host_parent_url,
    recoverable_root_http_status,
)


_RETURNED_ROOT_STATUS = re.compile(r"^listing request failed with status ([0-9]{3})$")


def _recoverable_http_exception(exc: requests.HTTPError) -> bool:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if recoverable_root_http_status(status_code):
        return True
    # Some generated connector transports construct an HTTPError without keeping
    # the Response object. Keep the fallback strict to an explicit leading 404/410
    # token in the transport message; other HTTP/network errors remain fatal.
    match = re.search(r"\b(404|410)\b", str(exc))
    return bool(match and recoverable_root_http_status(int(match.group(1))))


def _recoverable_returned_status(exc: RuntimeError) -> bool:
    match = _RETURNED_ROOT_STATUS.fullmatch(str(exc))
    return bool(match and recoverable_root_http_status(int(match.group(1))))


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

    The first call is completely unchanged. Recovery is attempted only when that
    call fails at its root request, because follow-up HTTP failures are already
    handled inside V4. The second call starts at the direct same-host parent and
    reuses the same metered executor and budgets. Runtime's hard request cap is
    therefore still the final authority and no request can be hidden or reset.
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
    except RuntimeError as exc:
        if not _recoverable_returned_status(exc):
            raise

    parent_url = direct_same_host_parent_url(listing_url, allowed_hosts=allowed_hosts)
    if not parent_url:
        raise RuntimeError("stale listing root has no authorized direct-parent recovery")

    return _acquire_genuine_job_pages(
        listing_url=parent_url,
        allowed_hosts=allowed_hosts,
        known_detail_urls=known_detail_urls,
        fetcher=fetcher,
        request_executor=request_executor,
        max_followup_requests=max_followup_requests,
        max_results=max_results,
    )


__all__ = ["acquire_genuine_job_pages"]
