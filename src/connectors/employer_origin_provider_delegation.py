"""Strict provider-matched detail delegation for acquisition proof.

This module performs no network I/O and grants no product or tenant authority.
It recognizes concrete canonical ATS detail URLs exposed by an already-authorized
employer/provider page only when the target host and route together form a strict
provider-specific detail contract. Final job truth still belongs to the caller's
genuine-job content proof.
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
_ABSOLUTE_PROVIDER_URL = re.compile(r"https?://[^\s\"'<>\\]+", flags=re.IGNORECASE)
_PROVIDER_DETAIL_ROUTE_PATTERNS: dict[str, re.Pattern[str]] = {
    "dvinci": re.compile(
        r"^/(?:[a-z]{2}(?:-[a-z]{2})?/)?jobs/[0-9]+/[^/?#]+/?$",
        flags=re.IGNORECASE,
    ),
    "personio": re.compile(
        r"^/job/[0-9]{2,20}/?$",
        flags=re.IGNORECASE,
    ),
    "smartrecruiters": re.compile(
        r"^/(?:ni/)?[A-Za-z0-9._-]{2,128}/(?:"
        r"[0-9]{8,}|"
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        r")-[^/?#]{3,}/?$",
        flags=re.IGNORECASE,
    ),
}
_EMBEDDED_DETAIL_PROVIDERS = frozenset({"personio", "smartrecruiters"})


def _host(value: str) -> str:
    return (urlparse(value).hostname or "").casefold().strip(".")


def _host_is_authorized(
    value: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> bool:
    normalized = {str(item).casefold().strip(".") for item in allowed_hosts if str(item)}
    return bool(_host(value) and _host(value) in normalized)


def _strict_provider_detail(provider: str, candidate: str) -> bool:
    pattern = _PROVIDER_DETAIL_ROUTE_PATTERNS.get(provider)
    if pattern is None:
        return False
    parsed = urlparse(candidate)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        return False
    recognition = recognize_ats_provider(candidate)
    if recognition is None or recognition.provider != provider:
        return False
    if provider == "personio" and recognition.target_hint is None:
        return False
    return bool(pattern.fullmatch(parsed.path or ""))


def explicit_canonical_provider_detail_urls(
    *,
    page_url: str,
    html: str,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = 5,
) -> tuple[tuple[str, str], ...]:
    """Return strict canonical ATS detail URLs explicitly embedded by an authorized page.

    Embedded/no-anchor authority is provider-specific rather than generic. It is
    enabled only for families whose current evidence proves that employers expose
    concrete public detail URLs in script/JSON state. The target must be HTTPS,
    cross-host, canonical for that provider, and match its strict public detail
    route. Provider-name text, inferred tenant names, board roots, internal routes,
    and non-canonical hosts cannot create delegation.
    """

    if limit < 1 or not _host_is_authorized(page_url, allowed_hosts):
        return ()

    decoded = unescape(html or "").replace(r"\/", "/")
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in _ABSOLUTE_PROVIDER_URL.findall(decoded):
        candidate = raw.strip().strip("\"'`),;]")
        parsed = urlparse(candidate)
        if parsed.scheme.casefold() != "https" or not parsed.hostname:
            continue
        if _host_is_authorized(candidate, allowed_hosts):
            continue
        recognition = recognize_ats_provider(candidate)
        if recognition is None or recognition.provider not in _EMBEDDED_DETAIL_PROVIDERS:
            continue
        normalized = candidate.split("#", 1)[0].rstrip("/")
        if normalized in seen or not _strict_provider_detail(recognition.provider, normalized):
            continue
        seen.add(normalized)
        result.append((recognition.provider, normalized))
        if len(result) >= limit:
            break
    return tuple(result)


def canonical_provider_delegated_detail_urls(
    *,
    provider: str,
    page_url: str,
    html: str,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = 5,
) -> tuple[str, ...]:
    """Return strict cross-host detail URLs for the same recognized ATS family.

    The source page must already be authorized. Visible anchors keep the existing
    provider-specific contract. For explicitly reviewed embedded-detail families,
    the same strict public route may also be accepted when the concrete absolute
    ATS detail URL is embedded in JSON/script state. Provider-name text alone never
    delegates a host.
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
        normalized = candidate.split("#", 1)[0].rstrip("/")
        if not _strict_provider_detail(provider, normalized):
            continue
        label = unescape(_TAG.sub(" ", raw_label))
        if not re.sub(r"\s+", " ", label).strip():
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= limit:
            return tuple(result)

    if provider not in _EMBEDDED_DETAIL_PROVIDERS:
        return tuple(result)

    for explicit_provider, candidate in explicit_canonical_provider_detail_urls(
        page_url=page_url,
        html=html,
        allowed_hosts=allowed_hosts,
        limit=limit,
    ):
        if explicit_provider != provider or candidate in seen:
            continue
        seen.add(candidate)
        result.append(candidate)
        if len(result) >= limit:
            break
    return tuple(result)


def canonical_provider_detail_host(*, provider: str, url: str) -> str | None:
    """Return the canonical target host only for a strict same-provider detail URL."""

    if not _strict_provider_detail(provider, url):
        return None
    return _host(url) or None


__all__ = [
    "canonical_provider_delegated_detail_urls",
    "canonical_provider_detail_host",
    "explicit_canonical_provider_detail_urls",
]
