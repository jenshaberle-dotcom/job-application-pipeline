"""Bounded recovery around the canonical V4 acquisition helper.

This wrapper adds exactly one recovery opportunity for an employer listing URL
that is proven stale by HTTP 404/410. The recovery target is not guessed: it is
the direct same-host path parent derived from the configured listing URL. The
recovered parent may then nominate exactly one explicit high-confidence job-board
link before control returns to the unchanged V4 acquisition helper.

The wrapper also carries narrowly evidenced root-redirect host bindings when a
configured employer career host has been observed to redirect to another exact
host owned by the same employer. These bindings are explicit pairs, not generic
registrable-domain inference, and therefore remain fail-closed for unrelated
hosts.

Finally, when the canonical helper exhausts its normal follow-ups on a failed
concrete detail request, this wrapper may use the still-unused shared fourth
request for exactly one already-discovered same-host sibling detail from the
immediately preceding successful page. No URL is guessed and no second extra
request is created.

The caller's metered request executor is shared throughout, so Runtime's absolute
request cap remains authoritative. No provider authority or acceptance widening
is created here.
"""

from __future__ import annotations

import re

import requests

from src.connectors.employer_origin_acquisition import (
    AcquiredJobPage,
    allowed_host,
    canonical_url,
    genuine_job_detail_proof,
    parse_page,
    url_host,
)
from src.connectors.employer_origin_acquisition_v4 import (
    EXTRA_FOLLOWUP_LIMIT,
    discover_navigation_candidates,
)
from src.connectors.employer_origin_acquisition_v4_forms import (
    MeteredRequest,
    acquire_genuine_job_pages as _acquire_genuine_job_pages,
)
from src.connectors.employer_origin_stale_root_recovery import (
    direct_same_host_parent_url,
    recoverable_root_http_status,
    strict_primary_listing_url,
)
from src.search_intelligence.multi_origin_evidence import job_detail_url_shape


_RETURNED_ROOT_STATUS = re.compile(r"^listing request failed with status ([0-9]{3})$")
_EXPLICIT_ROOT_REDIRECT_HOST_BINDINGS = {
    "careers.deloitte.com": "www.deloitte.com",
}

RecordedResponse = tuple[str, str, int]
RecordedAttempt = tuple[MeteredRequest, RecordedResponse | None]


def _effective_root_allowed_hosts(
    listing_url: str,
    allowed_hosts: tuple[str, ...],
) -> tuple[str, ...]:
    """Add only an exact, evidenced employer-owned root redirect host."""

    normalized = tuple(
        dict.fromkeys(str(item).casefold() for item in allowed_hosts if str(item))
    )
    source_host = url_host(listing_url)
    target_host = _EXPLICIT_ROOT_REDIRECT_HOST_BINDINGS.get(source_host)
    if not target_host or source_host not in set(normalized):
        return normalized
    return tuple(dict.fromkeys([*normalized, target_host]))


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


def _recorded_executor(request_executor, attempts: list[RecordedAttempt]):
    def execute(request: MeteredRequest):
        try:
            html, final_url, status_code = request_executor(request)
        except requests.RequestException:
            attempts.append((request, None))
            raise
        response = (str(html), str(final_url), int(status_code))
        attempts.append((request, response))
        return response

    return execute


def _recorded_fetcher(fetcher, attempts: list[RecordedAttempt]):
    def execute(url: str):
        request = MeteredRequest(url)
        try:
            html, final_url, status_code = fetcher(url)
        except requests.RequestException:
            attempts.append((request, None))
            raise
        response = (str(html), str(final_url), int(status_code))
        attempts.append((request, response))
        return response

    return execute


def _failed_detail_index(attempts: list[RecordedAttempt]) -> int | None:
    for index in range(len(attempts) - 1, 0, -1):
        request, response = attempts[index]
        failed = response is None or int(response[2]) >= 400
        if (
            failed
            and request.method.upper() == "GET"
            and not request.fields
            and job_detail_url_shape(request.url)
        ):
            return index
    return None


def _recover_failed_detail_sibling(
    *,
    attempts: list[RecordedAttempt],
    allowed_hosts: tuple[str, ...],
    fetcher,
    request_executor,
    max_followup_requests: int,
) -> AcquiredJobPage | None:
    """Use one unused bounded request for an already-observed same-host sibling."""

    max_total_requests = 1 + max_followup_requests + EXTRA_FOLLOWUP_LIMIT
    if len(attempts) >= max_total_requests:
        return None

    failed_index = _failed_detail_index(attempts)
    if failed_index is None:
        return None
    failed_request, _failed_response = attempts[failed_index]
    failed_host = url_host(failed_request.url)
    if not failed_host:
        return None

    source_page = None
    for prior_index in range(failed_index - 1, -1, -1):
        prior_request, prior_response = attempts[prior_index]
        if prior_response is None or int(prior_response[2]) >= 400:
            continue
        html, final_url, status_code = prior_response
        candidate_page = parse_page(
            requested_url=prior_request.url,
            html=html,
            final_url=final_url,
            status_code=status_code,
        )
        if allowed_host(candidate_page.final_url, allowed_hosts):
            source_page = candidate_page
            break
    if source_page is None:
        return None

    attempted_urls = {canonical_url(request.url) for request, _response in attempts}
    siblings = [
        candidate
        for candidate in discover_navigation_candidates(
            source_page,
            allowed_hosts=allowed_hosts,
            known_detail_urls=(),
        )
        if candidate.kind == "detail"
        and url_host(candidate.url) == failed_host
        and canonical_url(candidate.url) not in attempted_urls
    ]
    if not siblings:
        return None

    sibling = siblings[0]
    request = MeteredRequest(sibling.url)
    try:
        if request_executor is not None:
            html, final_url, status_code = request_executor(request)
        else:
            html, final_url, status_code = fetcher(request.url)
    except requests.RequestException:
        return None

    page = parse_page(
        requested_url=sibling.url,
        html=str(html),
        final_url=str(final_url),
        status_code=int(status_code),
    )
    if page.status_code >= 400 or not allowed_host(page.final_url, allowed_hosts):
        return None

    proof = genuine_job_detail_proof(
        page,
        allowed_hosts=allowed_hosts,
        known_detail=sibling.known_detail,
    )
    if not proof:
        return None

    return AcquiredJobPage(
        requested_url=page.requested_url,
        final_url=page.final_url,
        status_code=page.status_code,
        title=page.title,
        html_bytes=len(page.html.encode("utf-8")),
        proof_kind=proof,
        discovery_source=f"{sibling.discovery_source}_sibling_after_failed_detail",
        anchor_text=sibling.anchor_text,
    )


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
    """Run canonical V4 acquisition with two evidence-bounded recovery cases.

    A recovered stale parent is fetched exactly once. If it exposes exactly one
    explicit high-confidence job-board link, that URL becomes the new V4 root and
    the local follow-up budget is reduced by one because the parent fetch already
    consumed a metered request. This keeps stale-root -> parent -> listing -> detail
    inside Runtime's existing four-request ceiling.

    On a normal non-stale run, requests are recorded only to preserve causal page
    evidence. If canonical V4 returns no proof after a concrete detail request
    failed, one already-discovered same-host sibling from the immediately prior
    successful page may consume the still-available shared fourth request.

    If the stale parent has no unique primary listing link, the unchanged V4 helper
    runs from the already-fetched parent through a one-shot cache so the parent
    request is not counted twice. Any attempt beyond Runtime's global cap still
    fails closed in the existing bounded request executor.
    """

    effective_allowed_hosts = _effective_root_allowed_hosts(listing_url, allowed_hosts)
    attempts: list[RecordedAttempt] = []
    effective_executor = (
        _recorded_executor(request_executor, attempts)
        if request_executor is not None
        else None
    )
    effective_fetcher = (
        fetcher
        if request_executor is not None
        else _recorded_fetcher(fetcher, attempts)
    )

    try:
        jobs, observed_root = _acquire_genuine_job_pages(
            listing_url=listing_url,
            allowed_hosts=effective_allowed_hosts,
            known_detail_urls=known_detail_urls,
            fetcher=effective_fetcher,
            request_executor=effective_executor,
            max_followup_requests=max_followup_requests,
            max_results=max_results,
        )
        if jobs:
            return jobs, observed_root
        sibling = _recover_failed_detail_sibling(
            attempts=attempts,
            allowed_hosts=effective_allowed_hosts,
            fetcher=fetcher,
            request_executor=request_executor,
            max_followup_requests=max_followup_requests,
        )
        if sibling is not None:
            return [sibling], observed_root
        return jobs, observed_root
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

    parent_url = direct_same_host_parent_url(
        listing_url,
        allowed_hosts=effective_allowed_hosts,
    )
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
    if not allowed_host(parent_page.final_url, effective_allowed_hosts):
        raise RuntimeError("stale listing parent source binding mismatch")

    primary_listing = strict_primary_listing_url(
        parent_page,
        allowed_hosts=effective_allowed_hosts,
    )
    if primary_listing:
        return _acquire_genuine_job_pages(
            listing_url=primary_listing,
            allowed_hosts=effective_allowed_hosts,
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
            allowed_hosts=effective_allowed_hosts,
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
        allowed_hosts=effective_allowed_hosts,
        known_detail_urls=known_detail_urls,
        fetcher=cached_fetcher,
        request_executor=None,
        max_followup_requests=max_followup_requests,
        max_results=max_results,
    )


__all__ = ["acquire_genuine_job_pages"]
