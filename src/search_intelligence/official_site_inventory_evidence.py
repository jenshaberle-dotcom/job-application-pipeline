"""Bounded official-site inventory evidence from robots.txt and XML sitemaps.

This module is deliberately provider-neutral and read-only. It starts only from
already supplied official-domain evidence, never from LinkedIn/aggregator URLs.
It may follow same-organization hostnames within that official DNS suffix (for
example www.example.com -> careers.example.com), but it grants no source
authority itself. Returned URLs are merely search-result-shaped evidence for the
existing Employer-Origin scorer/proof.
"""

from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET
from typing import Callable, Sequence
from urllib.parse import urlparse, urlunparse

from src.search_intelligence.origin_jobspace_discovery import FetchedOriginPage
from src.search_intelligence.origin_source_discovery_agent import OriginSearchResult
from src.search_intelligence.origin_surface_evidence import CAREER_URL_MARKERS


MAX_OFFICIAL_ROOTS = 4
MAX_SITEMAP_DOCUMENTS = 6
MAX_NESTED_SITEMAPS_PER_INDEX = 3
MAX_SITEMAP_ITEMS = 2_000
MAX_EVIDENCE_URLS = 24
MAX_BODY_CHARS = 5_000_000


@dataclass(frozen=True)
class OfficialSiteInventoryResult:
    evidence: tuple[OriginSearchResult, ...]
    official_root_count: int
    robots_fetch_count: int
    sitemap_fetch_count: int
    sitemap_index_count: int
    sitemap_urlset_count: int
    candidate_url_count: int


def _local_name(tag: str) -> str:
    return str(tag or "").rsplit("}", 1)[-1].casefold()


def _normalized_https_root(value: str) -> str | None:
    parsed = urlparse(str(value or "").strip())
    host = (parsed.hostname or "").casefold().strip(".")
    if not host:
        return None
    return urlunparse(("https", host, "/", "", "", ""))


def _organization_suffix(host: str) -> str:
    normalized = host.casefold().strip(".")
    return normalized[4:] if normalized.startswith("www.") else normalized


def _same_organization_host(candidate_url: str, *, official_root: str) -> bool:
    candidate = urlparse(candidate_url)
    root = urlparse(official_root)
    candidate_host = (candidate.hostname or "").casefold().strip(".")
    root_host = (root.hostname or "").casefold().strip(".")
    suffix = _organization_suffix(root_host)
    return bool(
        candidate.scheme.casefold() == "https"
        and candidate_host
        and suffix
        and (
            candidate_host == suffix
            or candidate_host == root_host
            or candidate_host.endswith("." + suffix)
        )
    )


def _career_like_url(value: str) -> bool:
    parsed = urlparse(value)
    haystack = f"{parsed.hostname or ''} {parsed.path or ''}".casefold()
    return any(marker in haystack for marker in CAREER_URL_MARKERS)


def _robots_sitemaps(body: str, *, official_root: str) -> tuple[str, ...]:
    result: list[str] = []
    for raw_line in str(body or "").splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        name, raw_value = line.split(":", 1)
        if name.strip().casefold() != "sitemap":
            continue
        candidate = raw_value.strip()
        if not _same_organization_host(candidate, official_root=official_root):
            continue
        if candidate not in result:
            result.append(candidate)
        if len(result) >= MAX_SITEMAP_DOCUMENTS:
            break
    return tuple(result)


def _parse_sitemap_document(
    *,
    sitemap_url: str,
    body: str,
    official_root: str,
) -> tuple[str, tuple[str, ...]]:
    if not _same_organization_host(sitemap_url, official_root=official_root):
        return "invalid", ()
    if len((body or "").encode("utf-8")) > MAX_BODY_CHARS:
        return "invalid", ()
    try:
        root = ET.fromstring(body or "")
    except (ET.ParseError, ValueError):
        return "invalid", ()

    root_name = _local_name(root.tag)
    if root_name not in {"urlset", "sitemapindex"}:
        return "invalid", ()

    urls: list[str] = []
    seen: set[str] = set()
    container_name = "url" if root_name == "urlset" else "sitemap"
    for container in root.iter():
        if _local_name(container.tag) != container_name:
            continue
        if len(seen) >= MAX_SITEMAP_ITEMS:
            break
        loc = ""
        for child in container:
            if _local_name(child.tag) == "loc":
                loc = str(child.text or "").strip()
                break
        if not loc or loc in seen:
            continue
        if not _same_organization_host(loc, official_root=official_root):
            continue
        seen.add(loc)
        urls.append(loc)
    return root_name, tuple(urls)


def _standard_sitemap_urls(official_root: str) -> tuple[str, ...]:
    parsed = urlparse(official_root)
    host = (parsed.hostname or "").casefold()
    if not host:
        return ()
    return (
        f"https://{host}/sitemap.xml",
        f"https://{host}/sitemap_index.xml",
    )


def discover_official_site_inventory(
    *,
    company_name: str,
    official_domain_urls: Sequence[str],
    fetch_page: Callable[[str], FetchedOriginPage],
) -> OfficialSiteInventoryResult:
    """Collect bounded careers/jobspace URL evidence from official-site inventories."""

    roots: list[str] = []
    for raw in official_domain_urls:
        root = _normalized_https_root(raw)
        if root and root not in roots:
            roots.append(root)
        if len(roots) >= MAX_OFFICIAL_ROOTS:
            break

    evidence: list[OriginSearchResult] = []
    seen_evidence: set[str] = set()
    robots_fetch_count = 0
    sitemap_fetch_count = 0
    sitemap_index_count = 0
    sitemap_urlset_count = 0

    for official_root in roots:
        seed_sitemaps = list(_standard_sitemap_urls(official_root))

        robots_url = official_root.rstrip("/") + "/robots.txt"
        robots_page = fetch_page(robots_url)
        robots_fetch_count += 1
        if 200 <= robots_page.status_code < 400:
            for candidate in _robots_sitemaps(
                robots_page.html,
                official_root=official_root,
            ):
                if candidate not in seed_sitemaps:
                    seed_sitemaps.append(candidate)

        queue = seed_sitemaps[:MAX_SITEMAP_DOCUMENTS]
        visited: set[str] = set()
        while queue and sitemap_fetch_count < MAX_SITEMAP_DOCUMENTS * max(1, len(roots)):
            sitemap_url = queue.pop(0)
            if sitemap_url in visited:
                continue
            visited.add(sitemap_url)

            page = fetch_page(sitemap_url)
            sitemap_fetch_count += 1
            if not (200 <= page.status_code < 400):
                continue
            kind, urls = _parse_sitemap_document(
                sitemap_url=page.final_url or sitemap_url,
                body=page.html,
                official_root=official_root,
            )
            if kind == "sitemapindex":
                sitemap_index_count += 1
                admitted = 0
                for child in urls:
                    if child in visited or child in queue:
                        continue
                    queue.append(child)
                    admitted += 1
                    if admitted >= MAX_NESTED_SITEMAPS_PER_INDEX:
                        break
                continue
            if kind != "urlset":
                continue

            sitemap_urlset_count += 1
            for candidate in urls:
                if not _career_like_url(candidate):
                    continue
                if candidate in seen_evidence:
                    continue
                seen_evidence.add(candidate)
                evidence.append(
                    OriginSearchResult(
                        url=candidate,
                        title=f"{company_name} official careers inventory",
                        snippet=(
                            "URL declared by robots/sitemap evidence under an already "
                            "identified official company domain; normal Employer-Origin "
                            "identity and source proof remain required."
                        ),
                        provider="official_site_inventory",
                    )
                )
                if len(evidence) >= MAX_EVIDENCE_URLS:
                    break
            if len(evidence) >= MAX_EVIDENCE_URLS:
                break
        if len(evidence) >= MAX_EVIDENCE_URLS:
            break

    return OfficialSiteInventoryResult(
        evidence=tuple(evidence),
        official_root_count=len(roots),
        robots_fetch_count=robots_fetch_count,
        sitemap_fetch_count=sitemap_fetch_count,
        sitemap_index_count=sitemap_index_count,
        sitemap_urlset_count=sitemap_urlset_count,
        candidate_url_count=len(evidence),
    )


__all__ = [
    "OfficialSiteInventoryResult",
    "discover_official_site_inventory",
]
