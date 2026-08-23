"""Form-aware extension of the V4 deterministic acquisition proof lane.

This module preserves V4 host authority, genuine-job proof, and the single
shared extra-follow-up grant while allowing strict metered search forms,
provider-backed inventory fallbacks, and one explicit same-host job-link web-app
path. Network I/O remains injected by the caller; the helper never performs
requests itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import requests

from src.connectors.employer_origin_acquisition import (
    AcquiredJobPage,
    NavigationCandidate,
    PageSnapshot,
    allowed_host,
    canonical_url,
    explicit_root_delegated_listing_hosts,
    genuine_job_detail_proof,
    parse_page,
    url_host,
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
from src.connectors.employer_origin_explicit_job_link_inventory import (
    explicit_job_detail_urls_from_inventory,
    explicit_same_host_job_link_inventory_url,
    strict_same_host_application_script_url,
)
from src.connectors.employer_origin_form_navigation import (
    discover_strict_job_search_form_requests,
)
from src.connectors.employer_origin_sitemap_navigation import (
    sitemap_detail_urls,
    standard_same_host_sitemap_url,
)
from src.connectors.employer_origin_workday_navigation import (
    workday_board_route,
    workday_detail_urls_from_inventory,
    workday_inventory_json_fields,
)
from src.search_intelligence.ats_provider_registry import recognize_ats_provider


STRICT_FORM_SOURCE = "strict_job_search_form"
SUCCESSFACTORS_SITEMAP_SOURCE = "successfactors_standard_sitemap_inventory"
EXPLICIT_JOB_LINK_ASSET_SOURCE = "explicit_job_link_application_asset"
EXPLICIT_JOB_LINK_API_SOURCE = "explicit_job_link_inventory_api"
EXPLICIT_JOB_LINK_DETAIL_SOURCE = "explicit_job_link_inventory_detail"
WORKDAY_INVENTORY_SOURCE = "workday_provider_inventory"
WORKDAY_DETAIL_SOURCE = "workday_provider_inventory_detail"


@dataclass(frozen=True)
class MeteredRequest:
    url: str
    method: str = "GET"
    fields: tuple[tuple[str, str], ...] = ()
    json_fields: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True)
class MeteredNavigationCandidate:
    navigation: NavigationCandidate
    request: MeteredRequest
    context_url: str = ""

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
RequestKey = tuple[
    str,
    str,
    tuple[tuple[str, str], ...],
    tuple[tuple[str, str], ...],
]


def _request_for(candidate: QueueCandidate) -> MeteredRequest:
    if isinstance(candidate, MeteredNavigationCandidate):
        return candidate.request
    return MeteredRequest(candidate.url)


def _request_key(request: MeteredRequest) -> RequestKey:
    json_key = tuple(
        (
            str(name),
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
        for name, value in request.json_fields
    )
    return canonical_url(request.url), request.method.upper(), request.fields, json_key


def _execute_request(*, request: MeteredRequest, fetcher, request_executor):
    method = request.method.upper()
    if method not in {"GET", "POST"}:
        raise RuntimeError(f"unsupported acquisition request method: {method}")
    if request.fields and request.json_fields:
        raise RuntimeError("mixed form and JSON acquisition request payload")
    if request.json_fields and method != "POST":
        raise RuntimeError("JSON acquisition payload requires POST")
    if request_executor is not None:
        return request_executor(request)
    if method != "GET" or request.fields or request.json_fields:
        raise RuntimeError("metered request executor required for non-plain-GET acquisition")
    return fetcher(request.url)


def _strict_form_items(
    page: PageSnapshot,
    *,
    effective_allowed_hosts: tuple[str, ...],
    executed_requests: set[RequestKey],
    depth: int,
    request_executor,
) -> list[tuple[QueueCandidate, int]]:
    if request_executor is None:
        return []
    requests_found = discover_strict_job_search_form_requests(
        page_url=page.final_url,
        html=page.html,
        allowed_hosts=effective_allowed_hosts,
    )
    if len(requests_found) != 1:
        return []
    form = requests_found[0]
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


def _successfactors_sitemap_items(
    page: PageSnapshot,
    *,
    provider: str | None,
    effective_allowed_hosts: tuple[str, ...],
    fetched_urls: set[str],
    root_form_items: list[tuple[QueueCandidate, int]],
) -> list[tuple[QueueCandidate, int]]:
    """Prefer an explicit root search form; otherwise try one standard SF sitemap."""

    if provider != "successfactors" or root_form_items:
        return []
    sitemap_url = standard_same_host_sitemap_url(
        page_url=page.final_url,
        allowed_hosts=effective_allowed_hosts,
    )
    if not sitemap_url or canonical_url(sitemap_url) in fetched_urls:
        return []
    return [
        (
            NavigationCandidate(
                sitemap_url,
                "listing",
                SUCCESSFACTORS_SITEMAP_SOURCE,
                "",
                False,
            ),
            0,
        )
    ]


def _sitemap_stage_items(
    candidate: QueueCandidate,
    page: PageSnapshot,
    *,
    effective_allowed_hosts: tuple[str, ...],
    fetched_urls: set[str],
    depth: int,
) -> list[tuple[QueueCandidate, int]]:
    if candidate.discovery_source != SUCCESSFACTORS_SITEMAP_SOURCE:
        return []
    return [
        (
            NavigationCandidate(
                url,
                "detail",
                "successfactors_sitemap_detail",
                "",
                False,
            ),
            depth + 1,
        )
        for url in sitemap_detail_urls(
            sitemap_url=page.final_url,
            body=page.html,
            allowed_hosts=effective_allowed_hosts,
        )
        if canonical_url(url) not in fetched_urls
    ]


def _partition_explicit_delegated_provider_listings(
    items: list[tuple[QueueCandidate, int]],
    *,
    delegated_hosts: tuple[str, ...],
) -> tuple[list[tuple[QueueCandidate, int]], list[tuple[QueueCandidate, int]]]:
    """Rank an explicitly delegated canonical ATS board ahead of generic root forms."""

    delegated = {str(host).casefold().strip(".") for host in delegated_hosts if str(host)}
    provider_items: list[tuple[QueueCandidate, int]] = []
    fallback_items: list[tuple[QueueCandidate, int]] = []
    for item in items:
        candidate = item[0]
        recognition = recognize_ats_provider(candidate.url)
        if (
            candidate.kind == "listing"
            and url_host(candidate.url) in delegated
            and recognition is not None
        ):
            provider_items.append(item)
        else:
            fallback_items.append(item)
    return provider_items, fallback_items


def _workday_inventory_items(
    page: PageSnapshot,
    *,
    effective_allowed_hosts: tuple[str, ...],
    executed_requests: set[RequestKey],
    depth: int,
    request_executor,
) -> list[tuple[QueueCandidate, int]]:
    """Create exactly one metered first-page CXS inventory request."""

    if request_executor is None:
        return []
    route = workday_board_route(page.final_url, allowed_hosts=effective_allowed_hosts)
    if route is None:
        return []
    request = MeteredRequest(
        route.inventory_url,
        "POST",
        (),
        workday_inventory_json_fields(),
    )
    if _request_key(request) in executed_requests:
        return []
    navigation = NavigationCandidate(
        route.inventory_url,
        "listing",
        WORKDAY_INVENTORY_SOURCE,
        "",
        False,
    )
    return [
        (
            MeteredNavigationCandidate(
                navigation,
                request,
                context_url=route.public_board_url,
            ),
            depth + 1,
        )
    ]


def _workday_inventory_stage_items(
    candidate: QueueCandidate,
    page: PageSnapshot,
    *,
    effective_allowed_hosts: tuple[str, ...],
    fetched_urls: set[str],
    depth: int,
) -> list[tuple[QueueCandidate, int]]:
    if candidate.discovery_source != WORKDAY_INVENTORY_SOURCE:
        return []
    if not isinstance(candidate, MeteredNavigationCandidate) or not candidate.context_url:
        return []
    return [
        (
            NavigationCandidate(
                url,
                "detail",
                WORKDAY_DETAIL_SOURCE,
                "",
                True,
            ),
            depth + 1,
        )
        for url in workday_detail_urls_from_inventory(
            inventory_url=page.final_url,
            body=page.html,
            public_board_url=candidate.context_url,
            allowed_hosts=effective_allowed_hosts,
        )
        if canonical_url(url) not in fetched_urls
    ]


def _root_explicit_job_link_asset_items(
    root: PageSnapshot,
    *,
    effective_allowed_hosts: tuple[str, ...],
    fetched_urls: set[str],
    root_detail_items: list[tuple[QueueCandidate, int]],
    root_form_items: list[tuple[QueueCandidate, int]],
    root_listing_items: list[tuple[QueueCandidate, int]],
    root_greenhouse_items: list[tuple[QueueCandidate, int]],
    root_provider_items: list[tuple[QueueCandidate, int]],
) -> list[tuple[QueueCandidate, int]]:
    """Offer one strict app-asset route ahead of weak generic listing navigation."""

    if root_detail_items or root_form_items or root_greenhouse_items or root_provider_items:
        return []
    asset_url = strict_same_host_application_script_url(
        page_url=root.final_url,
        html=root.html,
        allowed_hosts=effective_allowed_hosts,
    )
    if not asset_url or canonical_url(asset_url) in fetched_urls:
        return []
    return [
        (
            NavigationCandidate(
                asset_url,
                "listing",
                EXPLICIT_JOB_LINK_ASSET_SOURCE,
                "",
                False,
            ),
            0,
        )
    ]


def _explicit_job_link_asset_stage_items(
    candidate: QueueCandidate,
    page: PageSnapshot,
    *,
    effective_allowed_hosts: tuple[str, ...],
    fetched_urls: set[str],
    depth: int,
) -> list[tuple[QueueCandidate, int]]:
    if candidate.discovery_source != EXPLICIT_JOB_LINK_ASSET_SOURCE:
        return []
    api_url = explicit_same_host_job_link_inventory_url(
        asset_url=page.final_url,
        javascript=page.html,
        allowed_hosts=effective_allowed_hosts,
    )
    if not api_url or canonical_url(api_url) in fetched_urls:
        return []
    return [
        (
            NavigationCandidate(
                api_url,
                "listing",
                EXPLICIT_JOB_LINK_API_SOURCE,
                "",
                False,
            ),
            depth + 1,
        )
    ]


def _explicit_job_link_api_stage_items(
    candidate: QueueCandidate,
    page: PageSnapshot,
    *,
    effective_allowed_hosts: tuple[str, ...],
    fetched_urls: set[str],
    depth: int,
) -> list[tuple[QueueCandidate, int]]:
    if candidate.discovery_source != EXPLICIT_JOB_LINK_API_SOURCE:
        return []
    return [
        (
            NavigationCandidate(
                url,
                "detail",
                EXPLICIT_JOB_LINK_DETAIL_SOURCE,
                "",
                True,
            ),
            depth + 1,
        )
        for url in explicit_job_detail_urls_from_inventory(
            api_url=page.final_url,
            body=page.html,
            allowed_hosts=effective_allowed_hosts,
        )
        if canonical_url(url) not in fetched_urls
    ]


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
    """Acquire genuine job proof with strict metered deterministic transitions.

    The base budget remains root + two follow-ups. Exactly one extra grant is
    shared across provider, query, form and explicit job-link transitions. The
    absolute caller-side request cap remains unchanged.
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

    root_discovered = list(
        discover_navigation_candidates(
            root,
            allowed_hosts=effective_allowed_hosts,
            known_detail_urls=known_detail_urls,
        )
    )
    root_detail_items: list[tuple[QueueCandidate, int]] = [
        (candidate, 0) for candidate in root_discovered if candidate.kind == "detail"
    ]
    raw_root_listing_items: list[tuple[QueueCandidate, int]] = [
        (candidate, 0) for candidate in root_discovered if candidate.kind != "detail"
    ]
    delegated_provider_listing_items, root_listing_items = (
        _partition_explicit_delegated_provider_listings(
            raw_root_listing_items,
            delegated_hosts=delegated_hosts,
        )
    )
    root_form_items = _strict_form_items(
        root,
        effective_allowed_hosts=effective_allowed_hosts,
        executed_requests=executed_requests,
        depth=-1,
        request_executor=request_executor,
    )
    root_greenhouse_items = list(_greenhouse_root_items(root, fetched=fetched_urls))
    root_provider, raw_root_provider_items = _provider_route_candidates(
        root,
        effective_allowed_hosts=effective_allowed_hosts,
        delegated_hosts=delegated_hosts,
        fetched=fetched_urls,
        depth=-1,
    )
    root_sitemap_items = _successfactors_sitemap_items(
        root,
        provider=root_provider,
        effective_allowed_hosts=effective_allowed_hosts,
        fetched_urls=fetched_urls,
        root_form_items=root_form_items,
    )
    root_provider_items: list[tuple[QueueCandidate, int]] = [
        *root_sitemap_items,
        *raw_root_provider_items,
    ]
    root_asset_items = _root_explicit_job_link_asset_items(
        root,
        effective_allowed_hosts=effective_allowed_hosts,
        fetched_urls=fetched_urls,
        root_detail_items=root_detail_items,
        root_form_items=root_form_items,
        root_listing_items=raw_root_listing_items,
        root_greenhouse_items=root_greenhouse_items,
        root_provider_items=root_provider_items,
    )

    queue: list[tuple[QueueCandidate, int]] = [
        *root_detail_items,
        *delegated_provider_listing_items,
        *root_form_items,
        *root_asset_items,
        *root_listing_items,
    ]

    if root_greenhouse_items and extra_followup_grants < EXTRA_FOLLOWUP_LIMIT:
        remaining += 1
        extra_followup_grants += 1
        queue = [*root_greenhouse_items, *queue]

    if root_provider_items and extra_followup_grants < EXTRA_FOLLOWUP_LIMIT:
        remaining += 1
        extra_followup_grants += 1
        if root_form_items:
            insert_at = next(
                (
                    index + 1
                    for index, (queued_candidate, _depth) in enumerate(queue)
                    if queued_candidate.discovery_source.startswith(f"{STRICT_FORM_SOURCE}_")
                ),
                0,
            )
            queue = [*queue[:insert_at], *root_provider_items, *queue[insert_at:]]
        else:
            queue = [*root_provider_items, *queue]

    results: list[AcquiredJobPage] = []

    while queue and remaining > 0 and len(results) < max_results:
        candidate, depth = queue.pop(0)
        request = _request_for(candidate)
        clean = canonical_url(candidate.url)
        request_key = _request_key(request)
        if not clean or request_key in executed_requests:
            continue
        if (
            request.method.upper() == "GET"
            and not request.fields
            and not request.json_fields
            and clean in fetched_urls
        ):
            continue

        candidate_hosts = _extend_provider_candidate_host(candidate, effective_allowed_hosts)
        if candidate_hosts is None:
            continue
        effective_allowed_hosts = candidate_hosts
        remaining -= 1
        try:
            html, final_url, status_code = _execute_request(
                request=request,
                fetcher=fetcher,
                request_executor=request_executor,
            )
        except requests.RequestException:
            executed_requests.add(request_key)
            fetched_urls.add(clean)
            if (
                candidate.discovery_source == EXPLICIT_JOB_LINK_ASSET_SOURCE
                and extra_followup_grants < EXTRA_FOLLOWUP_LIMIT
            ):
                remaining += 1
                extra_followup_grants += 1
            continue
        except Exception:
            executed_requests.add(request_key)
            fetched_urls.add(clean)
            if candidate.discovery_source == SUCCESSFACTORS_SITEMAP_SOURCE:
                continue
            raise
        executed_requests.add(request_key)
        fetched_urls.add(clean)
        fetched_urls.add(canonical_url(str(final_url)))

        page = parse_page(
            requested_url=candidate.url,
            html=str(html),
            final_url=str(final_url),
            status_code=int(status_code),
        )
        if page.status_code >= 400:
            if (
                candidate.discovery_source == EXPLICIT_JOB_LINK_ASSET_SOURCE
                and extra_followup_grants < EXTRA_FOLLOWUP_LIMIT
            ):
                remaining += 1
                extra_followup_grants += 1
            continue
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

        if candidate.discovery_source == WORKDAY_INVENTORY_SOURCE:
            workday_detail_items = _workday_inventory_stage_items(
                candidate,
                page,
                effective_allowed_hosts=effective_allowed_hosts,
                fetched_urls=fetched_urls,
                depth=depth,
            )
            if workday_detail_items:
                queue = [*workday_detail_items, *queue]
            continue

        if candidate.discovery_source == EXPLICIT_JOB_LINK_ASSET_SOURCE:
            api_items = _explicit_job_link_asset_stage_items(
                candidate,
                page,
                effective_allowed_hosts=effective_allowed_hosts,
                fetched_urls=fetched_urls,
                depth=depth,
            )
            if api_items:
                queue = [*api_items, *queue]
            elif extra_followup_grants < EXTRA_FOLLOWUP_LIMIT:
                remaining += 1
                extra_followup_grants += 1
            continue

        if candidate.discovery_source == EXPLICIT_JOB_LINK_API_SOURCE:
            explicit_detail_items = _explicit_job_link_api_stage_items(
                candidate,
                page,
                effective_allowed_hosts=effective_allowed_hosts,
                fetched_urls=fetched_urls,
                depth=depth,
            )
            if not explicit_detail_items:
                if extra_followup_grants < EXTRA_FOLLOWUP_LIMIT:
                    remaining += 1
                    extra_followup_grants += 1
                continue
            if remaining <= 0:
                if extra_followup_grants < EXTRA_FOLLOWUP_LIMIT:
                    remaining += 1
                    extra_followup_grants += 1
                    queue = [*explicit_detail_items, *queue]
                continue
            queue = [*explicit_detail_items, *queue]
            continue

        discovered = discover_navigation_candidates(
            page,
            allowed_hosts=effective_allowed_hosts,
            known_detail_urls=(),
        )
        sitemap_items = _sitemap_stage_items(
            candidate,
            page,
            effective_allowed_hosts=effective_allowed_hosts,
            fetched_urls=fetched_urls,
            depth=depth,
        )
        detail_items: list[tuple[QueueCandidate, int]] = [
            *sitemap_items,
            *[
                (item, depth + 1)
                for item in discovered
                if item.kind == "detail" and canonical_url(item.url) not in fetched_urls
            ],
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
            workday_items = _workday_inventory_items(
                page,
                effective_allowed_hosts=effective_allowed_hosts,
                executed_requests=executed_requests,
                depth=depth,
                request_executor=request_executor,
            )
            provider_items = [*workday_items, *raw_provider_items]
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
    "EXPLICIT_JOB_LINK_API_SOURCE",
    "EXPLICIT_JOB_LINK_ASSET_SOURCE",
    "EXPLICIT_JOB_LINK_DETAIL_SOURCE",
    "MeteredRequest",
    "STRICT_FORM_SOURCE",
    "SUCCESSFACTORS_SITEMAP_SOURCE",
    "WORKDAY_DETAIL_SOURCE",
    "WORKDAY_INVENTORY_SOURCE",
    "acquire_genuine_job_pages",
]
