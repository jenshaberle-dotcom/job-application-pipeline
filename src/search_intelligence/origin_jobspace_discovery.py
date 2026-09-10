"""Compose existing Origin discovery with bounded official-page surface evidence.

This is not a second source-validity engine. Both discovery passes delegate all
selection/scoring to :mod:`origin_source_discovery_agent`; this module only adds
provider-neutral evidence discovered from already plausible official company pages.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from src.search_intelligence.origin_source_discovery_agent import (
    OriginDiscoveryProbeResult,
    OriginDiscoveryResult,
    OriginSearchResult,
    discover_origin_source,
)
from src.search_intelligence.origin_surface_evidence import (
    OriginSurfaceEvidence,
    extract_origin_surface_evidence,
)


MAX_SURFACE_PAGES = 3
MAX_DISCOVERED_JOBSPACE_URLS = 24


@dataclass(frozen=True)
class FetchedOriginPage:
    requested_url: str
    final_url: str
    status_code: int
    html: str


@dataclass(frozen=True)
class OriginJobspaceDiscoveryResult:
    origin: OriginDiscoveryResult
    initial: OriginDiscoveryResult
    surface_page_count: int
    discovered_jobspace_url_count: int
    ats_families: tuple[str, ...]
    surface_evidence: tuple[tuple[str, OriginSurfaceEvidence], ...]
    official_domain_evidence_count: int


def _official_domain_search_results(
    *,
    company_name: str,
    official_domain_urls: Sequence[str],
) -> tuple[OriginSearchResult, ...]:
    return tuple(
        OriginSearchResult(
            url=url,
            title=f"{company_name} official website",
            snippet=f"Official-domain evidence for {company_name}; normal JAP proof still required.",
            provider="official_domain_evidence",
        )
        for url in official_domain_urls
        if str(url).strip()
    )


def _candidate_surface_urls(result: OriginDiscoveryResult) -> tuple[str, ...]:
    urls: list[str] = []
    for assessment in result.alternatives:
        if assessment.identity_score < 0.45:
            continue
        probe = assessment.probe
        if probe is not None and not probe.reachable:
            continue
        url = assessment.final_url or assessment.normalized_url
        if url and url not in urls:
            urls.append(url)
        if len(urls) >= MAX_SURFACE_PAGES:
            break
    return tuple(urls)


def _surface_search_results(
    *,
    company_name: str,
    source_url: str,
    evidence: OriginSurfaceEvidence,
) -> tuple[OriginSearchResult, ...]:
    results: list[OriginSearchResult] = []
    ats_by_url = {item.url: item.family for item in evidence.ats_fingerprints}
    for url in evidence.jobspace_urls[:MAX_DISCOVERED_JOBSPACE_URLS]:
        family = ats_by_url.get(url)
        descriptor = f" ATS family {family}" if family else " careers/jobspace link"
        results.append(
            OriginSearchResult(
                url=url,
                title=f"{company_name} official careers",
                snippet=(
                    f"Official company page {source_url} linked this{descriptor}. "
                    "Relationship evidence only; JAP company identity and source proof remain required."
                ),
                provider="official_page_surface",
            )
        )
    if evidence.canonical_url and evidence.canonical_url != source_url:
        results.append(
            OriginSearchResult(
                url=evidence.canonical_url,
                title=f"{company_name} canonical official careers page",
                snippet=f"Canonical URL declared by official page {source_url}.",
                provider="official_page_canonical",
            )
        )
    return tuple(results)


def discover_official_origin_jobspace(
    *,
    company_key: str,
    company_name: str,
    source_family_candidate: str | None = None,
    market_evidence_urls: Sequence[str] = (),
    search_results: Sequence[OriginSearchResult] = (),
    official_domain_urls: Sequence[str] = (),
    target_location: str | None = None,
    probe: Callable[[str], OriginDiscoveryProbeResult] | None = None,
    fetch_page: Callable[[str], FetchedOriginPage] | None = None,
    max_generated_candidates: int = 30,
) -> OriginJobspaceDiscoveryResult:
    """Discover the official Origin jobspace with one bounded evidence-expansion pass."""

    official_results = _official_domain_search_results(
        company_name=company_name,
        official_domain_urls=official_domain_urls,
    )
    base_results = tuple(search_results) + official_results
    initial = discover_origin_source(
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family_candidate,
        market_evidence_urls=market_evidence_urls,
        search_results=base_results,
        target_location=target_location,
        probe=probe,
        max_generated_candidates=max_generated_candidates,
    )

    if fetch_page is None:
        return OriginJobspaceDiscoveryResult(
            origin=initial,
            initial=initial,
            surface_page_count=0,
            discovered_jobspace_url_count=0,
            ats_families=(),
            surface_evidence=(),
            official_domain_evidence_count=len(official_results),
        )

    surface_rows: list[tuple[str, OriginSurfaceEvidence]] = []
    discovered_results: list[OriginSearchResult] = []
    ats_families: list[str] = []
    seen_discovered_urls: set[str] = set()

    for candidate_url in _candidate_surface_urls(initial):
        try:
            page = fetch_page(candidate_url)
        except Exception:
            continue
        if not (200 <= int(page.status_code) < 400) or not page.html:
            continue
        evidence = extract_origin_surface_evidence(
            html=page.html,
            base_url=page.final_url or candidate_url,
        )
        surface_rows.append((page.final_url or candidate_url, evidence))
        for match in evidence.ats_fingerprints:
            if match.family not in ats_families:
                ats_families.append(match.family)
        for item in _surface_search_results(
            company_name=company_name,
            source_url=page.final_url or candidate_url,
            evidence=evidence,
        ):
            if item.url in seen_discovered_urls:
                continue
            seen_discovered_urls.add(item.url)
            discovered_results.append(item)

    if not discovered_results:
        return OriginJobspaceDiscoveryResult(
            origin=initial,
            initial=initial,
            surface_page_count=len(surface_rows),
            discovered_jobspace_url_count=0,
            ats_families=tuple(ats_families),
            surface_evidence=tuple(surface_rows),
            official_domain_evidence_count=len(official_results),
        )

    refined = discover_origin_source(
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family_candidate,
        market_evidence_urls=market_evidence_urls,
        search_results=base_results + tuple(discovered_results),
        target_location=target_location,
        probe=probe,
        max_generated_candidates=max_generated_candidates,
    )
    return OriginJobspaceDiscoveryResult(
        origin=refined,
        initial=initial,
        surface_page_count=len(surface_rows),
        discovered_jobspace_url_count=len(discovered_results),
        ats_families=tuple(ats_families),
        surface_evidence=tuple(surface_rows),
        official_domain_evidence_count=len(official_results),
    )


__all__ = [
    "FetchedOriginPage",
    "OriginJobspaceDiscoveryResult",
    "discover_official_origin_jobspace",
]
