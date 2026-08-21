"""Deterministic acquisition proof lane with one tightly bounded extra hop.

V4 preserves the V3 genuine-job acceptance boundary while allowing exactly one
additional follow-up beyond the normal root + two-follow-up budget in two
high-confidence situations:

1. an already-authorized page exposes a strict deterministic provider route; or
2. the final already-authorized listing page exposes a trusted query-ID detail
   candidate that passed the strict generic query-detail extractor.

Provider-specific delegation never bypasses the acquisition fetcher. Greenhouse,
for example, may use the four-request sequence employer page -> board metadata ->
board jobs -> concrete detail only when the employer page itself exposes exactly
one canonical Greenhouse board token and metadata identity matches the employer
host. Every request therefore remains inside the same absolute request meter.

Provider-specific second-hop detail delegation likewise does not itself add
request budget: an already-authorized listing page may expose a concrete detail
only when the cross-host target is a canonical host of the same uniquely
recognized provider and matches that provider's strict detail route.

All budget-granting cases share one extra-hop grant, so the absolute request cap
remains four. No relevance qualification, persistence, provider call, or product
authority is introduced here.
"""

from __future__ import annotations

from src.connectors.employer_origin_acquisition import (
    AcquiredJobPage,
    NavigationCandidate,
    PageSnapshot,
    allowed_host,
    canonical_url,
    explicit_root_delegated_listing_hosts,
    extract_embedded_detail_urls,
    genuine_job_detail_proof,
    looks_like_listing_navigation,
    non_job_url,
    parse_page,
)
from src.connectors.employer_origin_ats_navigation import (
    authorized_ats_provider,
    provider_detail_urls,
    provider_listing_urls,
)
from src.connectors.employer_origin_greenhouse_navigation import (
    canonical_greenhouse_host,
    explicit_greenhouse_board_token,
    greenhouse_detail_urls_from_jobs,
    greenhouse_jobs_url,
    greenhouse_metadata_matches_employer,
    greenhouse_metadata_url,
)
from src.connectors.employer_origin_provider_delegation import (
    canonical_provider_delegated_detail_urls,
    canonical_provider_detail_host,
)
from src.search_intelligence.connector_feasibility_query_runtime import (
    extract_trusted_query_job_detail_links,
)
from src.search_intelligence.multi_origin_evidence import job_detail_url_shape


EXTRA_FOLLOWUP_LIMIT = 1
# Backward-compatible name retained for Runtime evidence contracts that predate
# the trusted-query boundary-hop case. All cases share the same single grant.
ATS_EXTRA_FOLLOWUP_LIMIT = EXTRA_FOLLOWUP_LIMIT
_PROVIDER_DELEGATED_DETAIL_SUFFIX = "_provider_delegated_detail"
_GREENHOUSE_METADATA_SOURCE = "greenhouse_provider_metadata"
_GREENHOUSE_JOBS_SOURCE = "greenhouse_provider_jobs"
_GREENHOUSE_DETAIL_SOURCE = "greenhouse_provider_delegated_detail"


def _add_candidate(
    target: list[NavigationCandidate],
    seen: set[str],
    *,
    url: str,
    kind: str,
    discovery_source: str,
    anchor_text: str = "",
    known_detail: bool = False,
    allowed_hosts: tuple[str, ...] | set[str],
) -> None:
    clean = canonical_url(url)
    if (
        not clean
        or clean in seen
        or not allowed_host(clean, allowed_hosts)
        or non_job_url(clean)
    ):
        return
    seen.add(clean)
    target.append(
        NavigationCandidate(
            clean,
            kind,
            discovery_source,
            anchor_text,
            known_detail,
        )
    )


def discover_navigation_candidates(
    page: PageSnapshot,
    *,
    allowed_hosts: tuple[str, ...] | set[str],
    known_detail_urls: tuple[str, ...] = (),
) -> tuple[NavigationCandidate, ...]:
    """Discover strict detail/query evidence before one generic listing hop."""

    current = canonical_url(page.final_url)
    seen: set[str] = {current}
    direct: list[NavigationCandidate] = []
    intermediate: list[NavigationCandidate] = []

    for url in known_detail_urls:
        _add_candidate(
            direct,
            seen,
            url=url,
            kind="detail",
            discovery_source="known_detail_evidence",
            known_detail=True,
            allowed_hosts=allowed_hosts,
        )

    for url, anchor_text in page.links:
        clean = canonical_url(url)
        if (
            not clean
            or clean in seen
            or not allowed_host(clean, allowed_hosts)
            or non_job_url(clean)
        ):
            continue
        if job_detail_url_shape(clean):
            _add_candidate(
                direct,
                seen,
                url=clean,
                kind="detail",
                discovery_source="anchor_detail",
                anchor_text=anchor_text,
                allowed_hosts=allowed_hosts,
            )
            continue
        if looks_like_listing_navigation(clean, anchor_text):
            _add_candidate(
                intermediate,
                seen,
                url=clean,
                kind="listing",
                discovery_source="anchor_listing",
                anchor_text=anchor_text,
                allowed_hosts=allowed_hosts,
            )

    for item in extract_trusted_query_job_detail_links(page.final_url, page.html):
        _add_candidate(
            direct,
            seen,
            url=item.url,
            kind="detail",
            discovery_source="query_detail",
            anchor_text=item.label,
            known_detail=True,
            allowed_hosts=allowed_hosts,
        )

    for clean in extract_embedded_detail_urls(
        page.html,
        page.final_url,
        allowed_hosts=allowed_hosts,
    ):
        _add_candidate(
            direct,
            seen,
            url=clean,
            kind="detail",
            discovery_source="embedded_detail",
            allowed_hosts=allowed_hosts,
        )

    return tuple([*direct, *intermediate])


def _provider_route_candidates(
    page: PageSnapshot,
    *,
    effective_allowed_hosts: tuple[str, ...],
    delegated_hosts: tuple[str, ...],
    fetched: set[str],
    depth: int,
) -> tuple[str | None, list[tuple[NavigationCandidate, int]]]:
    provider = authorized_ats_provider(
        page_url=page.final_url,
        html=page.html,
        allowed_hosts=effective_allowed_hosts,
        delegated_hosts=delegated_hosts,
    )
    if provider is None:
        return None, []

    detail_routes = provider_detail_urls(
        provider=provider,
        page_url=page.final_url,
        body=page.html,
        allowed_hosts=effective_allowed_hosts,
    )
    delegated_detail_routes = canonical_provider_delegated_detail_urls(
        provider=provider,
        page_url=page.final_url,
        html=page.html,
        allowed_hosts=effective_allowed_hosts,
    )
    listing_routes = provider_listing_urls(
        provider=provider,
        page_url=page.final_url,
        html=page.html,
        allowed_hosts=effective_allowed_hosts,
    )
    detail_items = [
        (
            NavigationCandidate(url, "detail", f"{provider}_provider_detail", "", False),
            depth + 1,
        )
        for url in detail_routes
        if canonical_url(url) not in fetched
    ]
    delegated_detail_items = [
        (
            NavigationCandidate(
                url,
                "detail",
                f"{provider}{_PROVIDER_DELEGATED_DETAIL_SUFFIX}",
                "",
                True,
            ),
            depth + 1,
        )
        for url in delegated_detail_routes
        if canonical_url(url) not in fetched
    ]
    listing_items = [
        (
            NavigationCandidate(url, "listing", f"{provider}_provider_listing", "", False),
            depth + 1,
        )
        for url in listing_routes
        if canonical_url(url) not in fetched
    ]
    return provider, [*detail_items, *delegated_detail_items, *listing_items]


def _greenhouse_root_items(
    page: PageSnapshot,
    *,
    fetched: set[str],
) -> list[tuple[NavigationCandidate, int]]:
    token = explicit_greenhouse_board_token(page.html)
    if not token:
        return []
    url = greenhouse_metadata_url(token)
    if not url or canonical_url(url) in fetched:
        return []
    return [
        (
            NavigationCandidate(
                url,
                "listing",
                f"{_GREENHOUSE_METADATA_SOURCE}:{token}",
                "",
                False,
            ),
            0,
        )
    ]


def _greenhouse_stage_items(
    candidate: NavigationCandidate,
    page: PageSnapshot,
    *,
    employer_url: str,
    fetched: set[str],
    depth: int,
) -> list[tuple[NavigationCandidate, int]]:
    source = candidate.discovery_source
    if source.startswith(f"{_GREENHOUSE_METADATA_SOURCE}:"):
        token = source.split(":", 1)[1]
        if not greenhouse_metadata_matches_employer(body=page.html, employer_url=employer_url):
            return []
        url = greenhouse_jobs_url(token)
        if not url or canonical_url(url) in fetched:
            return []
        return [
            (
                NavigationCandidate(
                    url,
                    "listing",
                    f"{_GREENHOUSE_JOBS_SOURCE}:{token}",
                    "",
                    False,
                ),
                depth + 1,
            )
        ]

    if source.startswith(f"{_GREENHOUSE_JOBS_SOURCE}:"):
        token = source.split(":", 1)[1]
        return [
            (
                NavigationCandidate(
                    url,
                    "detail",
                    f"{_GREENHOUSE_DETAIL_SOURCE}:{token}",
                    "",
                    True,
                ),
                depth + 1,
            )
            for url in greenhouse_detail_urls_from_jobs(body=page.html, board_token=token)
            if canonical_url(url) not in fetched
        ]
    return []


def _trusted_query_boundary_items(
    items: list[tuple[NavigationCandidate, int]],
) -> list[tuple[NavigationCandidate, int]]:
    return [
        item
        for item in items
        if item[0].kind == "detail"
        and item[0].known_detail
        and item[0].discovery_source == "query_detail"
    ]


def _extend_provider_candidate_host(
    candidate: NavigationCandidate,
    effective_allowed_hosts: tuple[str, ...],
) -> tuple[str, ...] | None:
    """Authorize only exact provider hosts encoded by internally derived route items."""

    source = candidate.discovery_source
    if source.startswith("greenhouse_provider_"):
        delegated_host = canonical_greenhouse_host(candidate.url)
        if not delegated_host:
            return None
        return tuple(dict.fromkeys([*effective_allowed_hosts, delegated_host]))

    if source.endswith(_PROVIDER_DELEGATED_DETAIL_SUFFIX):
        provider = source.removesuffix(_PROVIDER_DELEGATED_DETAIL_SUFFIX)
        delegated_host = canonical_provider_detail_host(provider=provider, url=candidate.url)
        if not delegated_host:
            return None
        return tuple(dict.fromkeys([*effective_allowed_hosts, delegated_host]))

    return effective_allowed_hosts if allowed_host(candidate.url, effective_allowed_hosts) else None


def acquire_genuine_job_pages(
    *,
    listing_url: str,
    allowed_hosts: tuple[str, ...],
    known_detail_urls: tuple[str, ...],
    fetcher,
    max_followup_requests: int = 2,
    max_results: int = 1,
) -> tuple[list[AcquiredJobPage], str]:
    """Acquire one genuine job with at most one strict extra follow-up."""

    if max_followup_requests < 0:
        raise ValueError("max_followup_requests must be >= 0")
    if max_results < 1:
        raise ValueError("max_results must be >= 1")

    listing_html, listing_final_url, listing_status = fetcher(listing_url)
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
    fetched: set[str] = {canonical_url(root.requested_url), canonical_url(root.final_url)}
    queue: list[tuple[NavigationCandidate, int]] = [
        (candidate, 0)
        for candidate in discover_navigation_candidates(
            root,
            allowed_hosts=effective_allowed_hosts,
            known_detail_urls=known_detail_urls,
        )
    ]

    root_greenhouse_items = _greenhouse_root_items(root, fetched=fetched)
    if root_greenhouse_items and extra_followup_grants < EXTRA_FOLLOWUP_LIMIT:
        remaining += 1
        extra_followup_grants += 1
        queue = [*root_greenhouse_items, *queue]

    _root_provider, root_provider_items = _provider_route_candidates(
        root,
        effective_allowed_hosts=effective_allowed_hosts,
        delegated_hosts=delegated_hosts,
        fetched=fetched,
        depth=-1,
    )
    if root_provider_items and extra_followup_grants < EXTRA_FOLLOWUP_LIMIT:
        remaining += 1
        extra_followup_grants += 1
        queue = [*root_provider_items, *queue]

    results: list[AcquiredJobPage] = []

    while queue and remaining > 0 and len(results) < max_results:
        candidate, depth = queue.pop(0)
        clean = canonical_url(candidate.url)
        if not clean or clean in fetched:
            continue
        candidate_hosts = _extend_provider_candidate_host(candidate, effective_allowed_hosts)
        if candidate_hosts is None:
            continue
        effective_allowed_hosts = candidate_hosts
        fetched.add(clean)
        remaining -= 1
        html, final_url, status_code = fetcher(candidate.url)
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
        detail_items = [
            (item, depth + 1)
            for item in discovered
            if item.kind == "detail" and canonical_url(item.url) not in fetched
        ]
        greenhouse_items = _greenhouse_stage_items(
            candidate,
            page,
            employer_url=root.final_url,
            fetched=fetched,
            depth=depth,
        )

        if remaining <= 0:
            boundary_items = _trusted_query_boundary_items(detail_items)
            if boundary_items and extra_followup_grants < EXTRA_FOLLOWUP_LIMIT:
                remaining += 1
                extra_followup_grants += 1
                queue = [*boundary_items, *queue]
            continue

        provider_items: list[tuple[NavigationCandidate, int]] = []
        if depth == 0:
            _provider, provider_items = _provider_route_candidates(
                page,
                effective_allowed_hosts=effective_allowed_hosts,
                delegated_hosts=delegated_hosts,
                fetched=fetched,
                depth=depth,
            )
            if provider_items and extra_followup_grants < EXTRA_FOLLOWUP_LIMIT:
                remaining += 1
                extra_followup_grants += 1

        queue = [*greenhouse_items, *detail_items, *provider_items, *queue]

    return results, root.final_url


__all__ = [
    "ATS_EXTRA_FOLLOWUP_LIMIT",
    "EXTRA_FOLLOWUP_LIMIT",
    "acquire_genuine_job_pages",
    "discover_navigation_candidates",
]
