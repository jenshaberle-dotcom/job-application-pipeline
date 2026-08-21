"""Strict provider-matched second-hop detail delegation for acquisition proof.

This module performs no network I/O and grants no product or tenant authority.
It only recognizes concrete detail links exposed by an already-authorized
provider-bearing listing page when the target host is a canonical host of that
same provider and the provider-specific detail route is strict.
"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin, urlparse

from src.search_intelligence.ats_provider_registry import recognize_ats_provider


_ANCHOR = re.compile(
    r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>",
    flags=re.IGNORECASE | re.DOTALL,
)
_TAG = re.compile(r"<[^>]+>")
_PROVIDER_DETAIL_ROUTE_PATTERNS: dict[str, re.Pattern[str]] = {
    "dvinci": re.compile(
        r"^/(?:[a-z]{2}(?:-[a-z]{2})?/)?jobs/[0-9]+/[^/?#]+/?$",
        flags=re.IGNORECASE,
    ),
}


def _host(value: str) -> str:
    return (urlparse(value).hostname or "").casefold().strip(".")


def _host_is_authorized(
    value: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> bool:
    normalized = {str(item).casefold().strip(".") for item in allowed_hosts if str(item)}
    return bool(_host(value) and _host(value) in normalized)


def canonical_provider_delegated_detail_urls(
    *,
    provider: str,
    page_url: str,
    html: str,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = 5,
) -> tuple[str, ...]:
    """Return strict cross-host detail links for the same recognized ATS family.

    The source page must already be authorized. The target must be HTTPS, live on
    a canonical host recognized as exactly the same provider, match the provider's
    strict detail route, and carry non-empty visible anchor text. A provider name
    in HTML alone never delegates a host.
    """

    route_pattern = _PROVIDER_DETAIL_ROUTE_PATTERNS.get(provider)
    if limit < 1 or route_pattern is None or not _host_is_authorized(page_url, allowed_hosts):
        return ()

    result: list[str] = []
    seen: set[str] = set()
    for raw_href, raw_label in _ANCHOR.findall(html):
        candidate = urljoin(page_url, unescape(raw_href).strip())
        parsed = urlparse(candidate)
        if parsed.scheme.casefold() != "https" or not parsed.hostname:
            continue
        if _host_is_authorized(candidate, allowed_hosts):
            continue
        recognition = recognize_ats_provider(candidate)
        if recognition is None or recognition.provider != provider:
            continue
        if not route_pattern.fullmatch(parsed.path or ""):
            continue
        label = unescape(_TAG.sub(" ", raw_label))
        if not re.sub(r"\s+", " ", label).strip():
            continue
        normalized = candidate.split("#", 1)[0].rstrip("/")
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= limit:
            break
    return tuple(result)


def canonical_provider_detail_host(*, provider: str, url: str) -> str | None:
    """Return the canonical target host only when it belongs to the same provider."""

    recognition = recognize_ats_provider(url)
    if recognition is None or recognition.provider != provider:
        return None
    parsed = urlparse(url)
    if parsed.scheme.casefold() != "https":
        return None
    return _host(url) or None


__all__ = [
    "canonical_provider_delegated_detail_urls",
    "canonical_provider_detail_host",
]
