"""Strict same-host sitemap inventory primitives for employer-origin acquisition.

This module performs no network I/O and grants no new host or product authority.
It only derives the standard ``/sitemap.xml`` URL on an already-authorized HTTPS
host and parses same-host URL inventories in memory. Concrete details are emitted
only when they already satisfy the canonical Pipeline job-detail URL shape.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from src.connectors.employer_origin_acquisition import allowed_host, canonical_url
from src.search_intelligence.multi_origin_evidence import job_detail_url_shape


MAX_SITEMAP_URLS = 10_000
MAX_DETAIL_URLS = 12


def _local_name(tag: str) -> str:
    return str(tag or "").rsplit("}", 1)[-1].casefold()


def standard_same_host_sitemap_url(
    *,
    page_url: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> str | None:
    """Derive only the standard HTTPS ``/sitemap.xml`` on an authorized host."""

    parsed = urlparse(page_url)
    hostname = (parsed.hostname or "").casefold().strip(".")
    if parsed.scheme.casefold() != "https" or not hostname:
        return None
    candidate = f"https://{hostname}/sitemap.xml"
    return candidate if allowed_host(candidate, allowed_hosts) else None


def sitemap_detail_urls(
    *,
    sitemap_url: str,
    body: str,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = MAX_DETAIL_URLS,
) -> tuple[str, ...]:
    """Extract strict same-host detail URLs from one fetched sitemap URL set.

    Sitemap indexes intentionally produce no details here. They need another
    explicitly bounded transition and therefore remain a separate future stage.
    """

    if limit < 1 or not allowed_host(sitemap_url, allowed_hosts):
        return ()
    parsed_url = urlparse(sitemap_url)
    if parsed_url.path.rstrip("/").casefold() != "/sitemap.xml":
        return ()

    try:
        root = ET.fromstring((body or "").encode("utf-8"))
    except (ET.ParseError, ValueError):
        return ()
    if _local_name(root.tag) != "urlset":
        return ()

    result: list[str] = []
    seen: set[str] = set()
    visited = 0
    for container in root.iter():
        if _local_name(container.tag) != "url":
            continue
        visited += 1
        if visited > MAX_SITEMAP_URLS:
            break
        loc = ""
        for child in container:
            if _local_name(child.tag) == "loc":
                loc = canonical_url(str(child.text or "").strip())
                break
        if not loc or loc in seen or not allowed_host(loc, allowed_hosts):
            continue
        parsed = urlparse(loc)
        if parsed.scheme.casefold() != "https" or not job_detail_url_shape(loc):
            continue
        seen.add(loc)
        result.append(loc)
        if len(result) >= min(limit, MAX_DETAIL_URLS):
            break
    return tuple(result)


__all__ = [
    "MAX_DETAIL_URLS",
    "sitemap_detail_urls",
    "standard_same_host_sitemap_url",
]
