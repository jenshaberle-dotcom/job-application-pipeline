"""Form-aware extension of the V4 deterministic acquisition proof lane.

This module preserves V4 host authority, genuine-job proof, and the single
shared extra-follow-up grant while allowing one strict HTML job-search form to
be represented as a metered GET/POST request. Network I/O remains injected by
the caller; the helper never performs requests itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.connectors.employer_origin_acquisition import (
    AcquiredJobPage,
    NavigationCandidate,
    PageSnapshot,
    allowed_host,
    canonical_url,
    explicit_root_delegated_listing_hosts,
    genuine_job_detail_proof,
    parse_page,
)
from src.connectors.employer_origin_acquisition_v4 import (
    EXTRA_FOLLOWUP_LIMIT,
    _extend_provider_candidate_host,
    _greenhouse_root_items,
    _greenhouse_stage_items,
    _provider_route_candidates,
    _trusted_query_boundary_items,
    discover_navigation_candidates,
)
from src.connectors.employer_origin_form_navigation import (
    discover_strict_job_search_form_requests,
)


STRICT_FORM_SOURCE = "strict_job_search_form"


@dataclass(frozen=True)
class MeteredRequest:
    url: str
    method: str = "GET"
    fields: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class MeteredNavigationCandidate:
    navigation: NavigationCandidate
    request: MeteredRequest

    @property
    def url(self) -> str:
        return self.navigation.url

    @property
    def kind(self) -> str:
        return self.navigation.kind

    @property
    def discovery_source(self) -> str:
        return self.navigation.discovery_source

    @property
    def anchor_text(self) -> str:
        return self.navigation.anchor_text

    @property
    def known_detail(self) -> bool:
        return self.navigation.known_detail


QueueCandidate = NavigationCandidate | MeteredNavigationCandidate


def _request_for(candidate: QueueCandidate) -> MeteredRequest:
    if isinstance(candidate, MeteredNavigationCandidate):
        return candidate.request
    return MeteredRequest(candidate.url)


def _request_key(request: MeteredRequest) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    return canonical_url(request.url), request.method.upper(), request.fields


def _execute_request(*, request: MeteredRequest, fetcher, request_executor):
    method = request.method.upper()
    if method not in {"GET", "POST"}:
        raise RuntimeError(f"unsupported acquisition request method: {method}")
    if request_executor is not None:
        return request_executor(request)
    if method != "GET" or request.fields:
        raise RuntimeError("metered request executor required for non-plain-GET acquisition")
    return fetcher(request.url)


def _strict_form_items(
    page: PageSnapshot,
    *,
    effective_allowed_hosts: tuple[str, ...],
    executed_requests: set[tuple[str, str, tuple[tuple[str, str], ...]]],
    depth: int,
    request_executor,
) -> list[tuple[QueueCandidate, int]]:
    if request_executor is None:
        return []
    requests = discover_strict_job_search_form_requests(
        page_url=page.final_url,
        html=page.html,
        allowed_hosts=effective_allowed_hosts,
    )
    if len(requests) != 1:
        return []
    form = requests[0]
    request = MeteredRequest(form.url, form.method, form.fields)
    if _request_key(request) in executed_requests:
        return []
    navigation = NavigationCandidate(
        form.url,
        "listing",
        f"{STRICT_FORM_SOURCE}_{form.method.casefold()}",
        "",
        False,
    )
    return [(MeteredNavigationCandidate(navigation, request), depth + 1)]


def acquire_genuine_job_pages(
    *,
    listing_url: str,
    allowed_hosts: tuple[str, ...],
    known_detail_urls: tuple[str, ...],
    fetcher,
    request_executor=None,
    max_followup_requests: int = 2,
    max_results: int = 1,
) -> tuple[list[AcquiredJobPage], str]:
    """Acquire genuine job proof with one strict metered form transition.

    The base budget remains root + two follow-ups. Exactly one extra grant is
    shared across V4 provider routes, trusted query-boundary detail proof, and
    the strict form-search transition. The absolute caller-side request cap is
    therefore unchanged.
    """

    if max_followup_requests < 0:
        raise ValueError("max_followup_requests must be >= 0")
    if max_results < 1:
        raise ValueError("max_results must be >= 1")

    root_request = MeteredRequest(listing_url)
    listing_html, listing_final_url, listing_status = _execute_request(
        request=root_request,
        fetcher=fetcher,
        request_executor=request_executor,
    )
    root = parse_page(
        requested_url=listing_url,
        html=str(listing_html),
        final_url=str(listing_final_url),
        status_code=int(listing_status),
    )
    if root.status_code >= 400:
        raise RuntimeError(f"listing request failed with status {root.status_code}")
    if not allowed_host(root.final_url, allowed_hosts):
        raise RuntimeError("listing source binding mismatch")

    root_known = canonical_url(listing_url) in {canonical_url(url) for url in known_detail_urls}
    root_proof = genuine_job_detail_proof(root, allowed_hosts=allowed_hosts, known_detail=root_known)
    if root_proof:
        return [
            AcquiredJobPage(
                requested_url=root.requested_url,
                final_url=root.final_url,
                status_code=root.status_code,
                title=root.title,
                html_bytes=len(root.html.encode("utf-8")),
                proof_kind=root_proof,
                discovery_source="listing_url_is_job_detail",
                anchor_text="",
            )
        ], root.final_url

    delegated_hosts = explicit_root_delegated_listing_hosts(root, allowed_hosts=allowed_hosts)
    effective_allowed_hosts = tuple(dict.fromkeys([*allowed_hosts, *delegated_hosts]))

    remaining = max_followup_requests
    extra_followup_grants = 0
    fetched_urls: set[str] = {canonical_url(root.requested_url), canonical_url(root.final_url)}
    executed_requests = {_request_key(root_request)}
    queue: list[tuple[QueueCandidate, int]] = [
        (candidate, 0)
        for candidate in discover_navigation_candidates(
            root,
            allowed_hosts=effective_allowed_hosts,
            known_detail_urls=known_detail_urls,
        )
    ]

    root_greenhouse_items = _greenhouse_root_items(root, fetched=fetched_urls)
    if root_greenhouse_items and extra_followup_grants < EXTRA_FOLLOWUP_LIMIT:
        remaining += 1
        extra_followup_grants += 1
        queue = [*root_greenhouse_items, *queue]

    _root_provider, root_provider_items = _provider_route_candidates(
        root,
        effective_allowed_hosts=effective_allowed_hosts,
        delegated_hosts=delegated_hosts,
        fetched=fetched_urls,
        depth=-1,
    )
    if root_provider_items and extra_followup_grants < EXTRA_FOLLOWUP_LIMIT:
        remaining += 1
        extra_followup_grants += 1
        queue = [*root_provider_items, *queue]

    results: list[AcquiredJobPage] = []

    while queue and remaining > 0 and len(results) < max_results:
        candidate, depth = queue.pop(0)
        request = _request_for(candidate)
        clean = canonical_url(candidate.url)
        request_key = _request_key(request)
        if not clean or request_key in executed_requests:
            continue
        if request.method.upper() == "GET" and not request.fields and clean in fetched_urls:
            continue

        candidate_hosts = _extend_provider_candidate_host(candidate, effective_allowed_hosts)
        if candidate_hosts is None:
            continue
        effective_allowed_hosts = candidate_hosts
        remaining -= 1
        html, final_url, status_code = _execute_request(
            request=request,
            fetcher=fetcher,
            request_executor=request_executor,
        )
        executed_requests.add(request_key)
        fetched_urls.add(clean)
        fetched_urls.add(canonical_url(str(final_url)))

        page = parse_page(
            requested_url=candidate.url,
            html=str(html),
            final_url=str(final_url),
            status_code=int(status_code),
        )
        proof = genuine_job_detail_proof(
            page,
            allowed_hosts=effective_allowed_hosts,
            known_detail=candidate.known_detail,
        )
        if proof:
            results.append(
                AcquiredJobPage(
                    requested_url=page.requested_url,
                    final_url=page.final_url,
                    status_code=page.status_code,
                    title=page.title,
                    html_bytes=len(page.html.encode("utf-8")),
                    proof_kind=proof,
                    discovery_source=candidate.discovery_source,
                    anchor_text=candidate.anchor_text,
                )
            )
            continue

        if candidate.kind != "listing":
            continue

        discovered = discover_navigation_candidates(
            page,
            allowed_hosts=effective_allowed_hosts,
            known_detail_urls=(),
        )
        detail_items: list[tuple[QueueCandidate, int]] = [
            (item, depth + 1)
            for item in discovered
            if item.kind == "detail" and canonical_url(item.url) not in fetched_urls
        ]
        greenhouse_items: list[tuple[QueueCandidate, int]] = list(
            _greenhouse_stage_items(
                candidate,
                page,
                employer_url=root.final_url,
                fetched=fetched_urls,
                depth=depth,
            )
        )

        if remaining <= 0:
            boundary_items = _trusted_query_boundary_items(detail_items)
            if boundary_items and extra_followup_grants < EXTRA_FOLLOWUP_LIMIT:
                remaining += 1
                extra_followup_grants += 1
                queue = [*boundary_items, *queue]
            continue

        provider_items: list[tuple[QueueCandidate, int]] = []
        if depth == 0:
            _provider, raw_provider_items = _provider_route_candidates(
                page,
                effective_allowed_hosts=effective_allowed_hosts,
                delegated_hosts=delegated_hosts,
                fetched=fetched_urls,
                depth=depth,
            )
            provider_items = list(raw_provider_items)
            if provider_items and extra_followup_grants < EXTRA_FOLLOWUP_LIMIT:
                remaining += 1
                extra_followup_grants += 1

        form_items: list[tuple[QueueCandidate, int]] = []
        if depth == 0:
            form_items = _strict_form_items(
                page,
                effective_allowed_hosts=effective_allowed_hosts,
                executed_requests=executed_requests,
                depth=depth,
                request_executor=request_executor,
            )
            if form_items and extra_followup_grants < EXTRA_FOLLOWUP_LIMIT:
                remaining += 1
                extra_followup_grants += 1

        queue = [*greenhouse_items, *detail_items, *provider_items, *form_items, *queue]

    return results, root.final_url


__all__ = [
    "MeteredRequest",
    "STRICT_FORM_SOURCE",
    "acquire_genuine_job_pages",
]
