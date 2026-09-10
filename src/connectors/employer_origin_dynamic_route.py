"""Strict generic bridge from employer-controlled dynamic evidence to job routes.

This module turns URL-shaped evidence already exposed by an authorized Employer-
Origin page or an exact-host dynamic endpoint into bounded acquisition candidates.
It does not infer IDs, execute JavaScript, name employers, or treat script/API text
as proof. A concrete detail still has to be fetched and pass the unchanged genuine
job-detail proof before Product admission.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from src.connectors.employer_origin_acquisition import allowed_host, canonical_url, non_job_url
from src.search_intelligence.connector_feasibility import (
    KNOWN_AGGREGATOR_DOMAINS,
    SOCIAL_OR_EXTERNAL_NOISE_DOMAINS,
)
from src.search_intelligence.dynamic_surface_evidence import extract_dynamic_route_literals
from src.search_intelligence.multi_origin_evidence import job_detail_url_shape

MAX_DYNAMIC_LISTING_ROUTES = 4
MAX_DYNAMIC_DETAIL_ROUTES = 12
_DYNAMIC_LISTING_MARKERS = (
    "serverless",
    "/api/",
    "/api",
    "graphql",
    "jobs",
    "positions",
    "vacanc",
    "stellen",
    "openings",
)
_STRONG_DYNAMIC_DETAIL_PATHS = (
    re.compile(r"/(?:jobs?|positions?)/[a-z0-9_-]{2,}/(?:job|position)?/?$", re.IGNORECASE),
    re.compile(r"/jobposting/[a-z0-9_-]{12,}(?:/apply)?/?$", re.IGNORECASE),
)


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").casefold().strip(".")


def _registered_domain(url: str) -> str:
    host = _host(url).removeprefix("www.")
    parts = [part for part in host.split(".") if part]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _same_registered_domain(left: str, right: str) -> bool:
    domain = _registered_domain(left)
    return bool(domain and domain == _registered_domain(right))


def _public_https(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    return bool(
        parsed.scheme.casefold() == "https"
        and host
        and not parsed.username
        and not parsed.password
        and host not in KNOWN_AGGREGATOR_DOMAINS
        and host not in SOCIAL_OR_EXTERNAL_NOISE_DOMAINS
        and host not in {"localhost", "127.0.0.1", "0.0.0.0"}
    )


def _trusted_job_host(url: str) -> bool:
    labels = [part for part in _host(url).split(".") if part]
    return any(
        label in {"job", "jobs", "career", "careers", "karriere", "recruit", "recruiting"}
        or label.startswith(("job-", "jobs-", "career-", "careers-", "karriere-", "recruit-"))
        for label in labels
    )


def _strong_detail_shape(url: str) -> bool:
    if job_detail_url_shape(url):
        return True
    path = urlparse(url).path
    return any(pattern.search(path) for pattern in _STRONG_DYNAMIC_DETAIL_PATHS)


def _listing_priority(url: str) -> tuple[int, str]:
    parsed = urlparse(url)
    surface = f"{parsed.path}?{parsed.query}".casefold()
    for index, marker in enumerate(_DYNAMIC_LISTING_MARKERS):
        if marker in surface:
            return index, surface
    return len(_DYNAMIC_LISTING_MARKERS), surface


def dynamic_listing_urls(
    *,
    page_url: str,
    body: str,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = MAX_DYNAMIC_LISTING_ROUTES,
) -> tuple[str, ...]:
    """Return exact-authorized-host dynamic inventory/API routes from page evidence."""

    current = canonical_url(page_url)
    values: list[str] = []
    for item in extract_dynamic_route_literals(text=body, base_url=page_url):
        url = canonical_url(item.normalized_url or "")
        if not url or url == current or not _public_https(url):
            continue
        if not allowed_host(url, allowed_hosts) or non_job_url(url):
            continue
        path_query = f"{urlparse(url).path}?{urlparse(url).query}".casefold()
        if not any(marker in path_query for marker in _DYNAMIC_LISTING_MARKERS):
            continue
        if _strong_detail_shape(url):
            continue
        if url not in values:
            values.append(url)
    values.sort(key=_listing_priority)
    return tuple(values[: max(0, limit)])


def dynamic_detail_urls(
    *,
    page_url: str,
    body: str,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = MAX_DYNAMIC_DETAIL_ROUTES,
) -> tuple[str, ...]:
    """Return explicit concrete details from an already-authorized page/endpoint.

    Cross-host candidates are accepted only when the URL itself has a strong job
    detail shape and either remains in the employer's registered-domain namespace
    or lands on a job/career-labelled host. This is evidence for one exact target,
    not permission to crawl that host.
    """

    values: list[str] = []
    for item in extract_dynamic_route_literals(text=body, base_url=page_url):
        url = canonical_url(item.normalized_url or "")
        if not url or not _public_https(url) or non_job_url(url):
            continue
        if not _strong_detail_shape(url):
            continue
        if not (
            allowed_host(url, allowed_hosts)
            or _same_registered_domain(page_url, url)
            or _trusted_job_host(url)
        ):
            continue
        if url not in values:
            values.append(url)
        if len(values) >= max(0, limit):
            break
    return tuple(values)


def dynamic_delegated_detail_host(
    *,
    evidence_page_url: str,
    detail_url: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> str | None:
    """Authorize only the exact host of one already-derived dynamic detail URL."""

    if allowed_host(detail_url, allowed_hosts):
        return _host(detail_url)
    if not _public_https(detail_url) or not _strong_detail_shape(detail_url):
        return None
    if not (
        _same_registered_domain(evidence_page_url, detail_url)
        or _trusted_job_host(detail_url)
    ):
        return None
    return _host(detail_url) or None


__all__ = [
    "dynamic_delegated_detail_host",
    "dynamic_detail_urls",
    "dynamic_listing_urls",
]
