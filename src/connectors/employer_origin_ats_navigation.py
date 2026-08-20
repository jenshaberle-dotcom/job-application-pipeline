"""Provider-aware deterministic navigation for employer-origin acquisition proof.

This module performs no network I/O and grants no employer, tenant, product, or
qualification authority. Callers may use it only after source-host binding has
already been established. It recognizes a bounded ATS family from the already
fetched page and exposes provider-specific listing routes that are visible in
that same response.
"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin, urlparse

from src.search_intelligence.ats_provider_registry import (
    classify_provider_names,
    recognize_ats_provider,
)


RECRUITING_HOST_LABELS = {
    "job",
    "jobs",
    "career",
    "careers",
    "karriere",
    "recruiting",
    "recruitment",
}

_SUCCESSFACTORS_GO_ROUTE = re.compile(
    r"^/go/[^/?#]+/[0-9]+/?$",
    flags=re.IGNORECASE,
)
_ANCHOR = re.compile(
    r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>",
    flags=re.IGNORECASE | re.DOTALL,
)


def _host(value: str) -> str:
    return (urlparse(value).hostname or "").casefold().strip(".")


def _host_is_authorized(
    value: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> bool:
    normalized = {str(item).casefold().strip(".") for item in allowed_hosts if str(item)}
    return bool(_host(value) and _host(value) in normalized)


def _recruiting_host(value: str) -> bool:
    labels = {part for part in _host(value).split(".") if part}
    return bool(labels.intersection(RECRUITING_HOST_LABELS))


def authorized_ats_provider(
    *,
    page_url: str,
    html: str,
    allowed_hosts: tuple[str, ...] | set[str],
    delegated_hosts: tuple[str, ...] | set[str] = (),
) -> str | None:
    """Recognize one ATS family without widening already-established host authority.

    Canonical ATS host suffixes are accepted directly. Branded/CNAME recruiting
    hosts are accepted only when the host is already source-authorized and is
    either an explicit employer-root delegation or has an explicit recruiting
    hostname label. Ambiguous multi-provider evidence fails closed.
    """

    if not _host_is_authorized(page_url, allowed_hosts):
        return None

    direct = recognize_ats_provider(page_url)
    if direct is not None:
        return direct.provider

    page_host = _host(page_url)
    delegated = {
        str(item).casefold().strip(".") for item in delegated_hosts if str(item)
    }
    if page_host not in delegated and not _recruiting_host(page_url):
        return None

    providers = classify_provider_names(html[:500_000])
    if len(providers) != 1:
        return None
    return providers[0]


def provider_listing_urls(
    *,
    provider: str,
    page_url: str,
    html: str,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = 5,
) -> tuple[str, ...]:
    """Return bounded same-host provider-specific listing routes from one page.

    The first supported family is SuccessFactors. Its static career landing pages
    commonly expose country/category routes shaped as ``/go/<slug>/<numeric-id>/``.
    These are listing routes only; callers must still fetch a concrete detail page
    and pass the canonical genuine-job proof before acquisition can succeed.
    """

    if limit < 1 or provider != "successfactors":
        return ()
    if not _host_is_authorized(page_url, allowed_hosts):
        return ()

    current = page_url.split("#", 1)[0].rstrip("/")
    result: list[str] = []
    seen: set[str] = set()
    for raw_href, _raw_label in _ANCHOR.findall(html):
        candidate = urljoin(page_url, unescape(raw_href).strip())
        parsed = urlparse(candidate)
        if parsed.scheme.casefold() != "https" or not parsed.hostname:
            continue
        if not _host_is_authorized(candidate, allowed_hosts):
            continue
        normalized = candidate.split("#", 1)[0].rstrip("/")
        if normalized == current or normalized in seen:
            continue
        if not _SUCCESSFACTORS_GO_ROUTE.fullmatch(parsed.path or ""):
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= limit:
            break
    return tuple(result)


__all__ = [
    "authorized_ats_provider",
    "provider_listing_urls",
]
