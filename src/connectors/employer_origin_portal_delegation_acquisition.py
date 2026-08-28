"""Acquire through one evidence-bounded employer -> career portal handoff.

This is an additive residual bridge, not a replacement for the canonical V4
acquirer.  Callers should invoke it only after the ordinary deterministic path
failed.  It consumes one employer-root GET to prove exactly one strong portal CTA,
then hands that exact URL to the existing V4 form-aware acquisition stack with the
remaining request budget.

No portal URL or host is guessed.  Ambiguous or weak evidence fails closed.
"""

from __future__ import annotations

from src.connectors.employer_origin_acquisition import (
    AcquiredJobPage,
    allowed_host,
    canonical_url,
    parse_page,
    url_host,
)
from src.connectors.employer_origin_acquisition_v4_forms import (
    MeteredRequest,
    acquire_genuine_job_pages as _acquire_genuine_job_pages,
)
from src.connectors.employer_origin_portal_delegation import (
    explicit_bounded_portal_urls,
)


def _execute_root(*, listing_url: str, fetcher, request_executor):
    if request_executor is not None:
        return request_executor(MeteredRequest(listing_url))
    return fetcher(listing_url)


def acquire_via_explicit_portal(
    *,
    listing_url: str,
    allowed_hosts: tuple[str, ...],
    known_detail_urls: tuple[str, ...],
    fetcher,
    request_executor=None,
    max_followup_requests: int = 2,
    max_results: int = 1,
) -> tuple[list[AcquiredJobPage], str]:
    """Attempt exactly one strict CTA-bound portal handoff.

    With the normal ``max_followup_requests=2`` contract, one request is consumed
    proving the employer root and the downstream V4 call receives one normal
    follow-up.  V4's existing single shared evidence grant may still operate, so a
    caller-side absolute cap of four remains authoritative.
    """

    if max_followup_requests < 1:
        return [], listing_url
    if max_results < 1:
        raise ValueError("max_results must be >= 1")

    root_html_raw, root_final_raw, root_status_raw = _execute_root(
        listing_url=listing_url,
        fetcher=fetcher,
        request_executor=request_executor,
    )
    root = parse_page(
        requested_url=listing_url,
        html=str(root_html_raw),
        final_url=str(root_final_raw),
        status_code=int(root_status_raw),
    )
    if root.status_code >= 400:
        return [], root.final_url
    if not allowed_host(root.final_url, allowed_hosts):
        raise RuntimeError("portal bridge root source binding mismatch")

    portals = explicit_bounded_portal_urls(
        root,
        allowed_hosts=allowed_hosts,
        limit=2,
    )
    if len(portals) != 1:
        return [], root.final_url

    portal_url = canonical_url(portals[0])
    portal_host = url_host(portal_url)
    if not portal_host:
        return [], root.final_url

    effective_allowed_hosts = tuple(dict.fromkeys([*allowed_hosts, portal_host]))
    jobs, observed_portal = _acquire_genuine_job_pages(
        listing_url=portal_url,
        allowed_hosts=effective_allowed_hosts,
        known_detail_urls=known_detail_urls,
        fetcher=fetcher,
        request_executor=request_executor,
        max_followup_requests=max_followup_requests - 1,
        max_results=max_results,
    )
    return jobs, observed_portal


__all__ = ["acquire_via_explicit_portal"]
