"""ATS-aware deterministic acquisition proof lane.

V4 preserves the V3 genuine-job acceptance boundary while testing one narrower
navigation hypothesis: after an employer-bound recruiting host is reached, a
recognized ATS family may expose one additional deterministic listing route.

The normal budget remains one root request plus two follow-ups. Exactly one extra
follow-up can be granted only when the already-authorized page is recognized as a
supported ATS family and exposes a provider-specific bounded listing route in the
same response. No relevance qualification, persistence, provider call, or product
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
    provider_listing_urls,
)
from src.search_intelligence.connector_feasibility_query_runtime import (
    extract_trusted_query_job_detail_links,
)
from src.search_intelligence.multi_origin_evidence import job_detail_url_shape


ATS_EXTRA_FOLLOWUP_LIMIT = 1


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
    """Discover strict detail/query evidence before one generic listing hop.

    V4 intentionally does not reuse the broader feasibility classifier. That
    classifier is useful for build planning but the 40-connector acquisition run
    showed that it can spend the tiny proof budget on career-context pages. V4
    keeps only the independently bounded query-ID extractor from that layer.
    """

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

    routes = provider_listing_urls(
        provider=provider,
        page_url=page.final_url,
        html=page.html,
        allowed_hosts=effective_allowed_hosts,
    )
    items = [
        (
            NavigationCandidate(
                url,
                "listing",
                f"{provider}_provider_listing",
                "",
                False,
            ),
            depth + 1,
        )
        for url in routes
        if canonical_url(url) not in fetched
    ]
    return provider, items


def acquire_genuine_job_pages(
    *,
    listing_url: str,
    allowed_hosts: tuple[str, ...],
    known_detail_urls: tuple[str, ...],
    fetcher,
    max_followup_requests: int = 2,
    max_results: int = 1,
) -> tuple[list[AcquiredJobPage], str]:
    """Acquire one genuine job with one optional provider-recognized extra hop."""

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

    root_known = canonical_url(listing_url) in {
        canonical_url(url) for url in known_detail_urls
    }
    root_proof = genuine_job_detail_proof(
        root,
        allowed_hosts=allowed_hosts,
        known_detail=root_known,
    )
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

    delegated_hosts = explicit_root_delegated_listing_hosts(
        root,
        allowed_hosts=allowed_hosts,
    )
    effective_allowed_hosts = tuple(dict.fromkeys([*allowed_hosts, *delegated_hosts]))

    remaining = max_followup_requests
    ats_extra_grants = 0
    fetched: set[str] = {
        canonical_url(root.requested_url),
        canonical_url(root.final_url),
    }
    queue: list[tuple[NavigationCandidate, int]] = [
        (candidate, 0)
        for candidate in discover_navigation_candidates(
            root,
            allowed_hosts=effective_allowed_hosts,
            known_detail_urls=known_detail_urls,
        )
    ]

    _root_provider, root_provider_items = _provider_route_candidates(
        root,
        effective_allowed_hosts=effective_allowed_hosts,
        delegated_hosts=delegated_hosts,
        fetched=fetched,
        depth=-1,
    )
    if root_provider_items and ats_extra_grants < ATS_EXTRA_FOLLOWUP_LIMIT:
        remaining += 1
        ats_extra_grants += 1
        queue = [*root_provider_items, *queue]

    results: list[AcquiredJobPage] = []

    while queue and remaining > 0 and len(results) < max_results:
        candidate, depth = queue.pop(0)
        clean = canonical_url(candidate.url)
        if not clean or clean in fetched:
            continue
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

        if candidate.kind != "listing" or remaining <= 0:
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

        provider_items: list[tuple[NavigationCandidate, int]] = []
        if depth == 0:
            _provider, provider_items = _provider_route_candidates(
                page,
                effective_allowed_hosts=effective_allowed_hosts,
                delegated_hosts=delegated_hosts,
                fetched=fetched,
                depth=depth,
            )
            if provider_items and ats_extra_grants < ATS_EXTRA_FOLLOWUP_LIMIT:
                remaining += 1
                ats_extra_grants += 1

        queue = [*detail_items, *provider_items, *queue]

    return results, root.final_url


__all__ = [
    "ATS_EXTRA_FOLLOWUP_LIMIT",
    "acquire_genuine_job_pages",
    "discover_navigation_candidates",
]
