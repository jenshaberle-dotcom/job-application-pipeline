"""Bounded learning evidence for JavaScript-backed Employer-Origin surfaces.

This module does not establish source validity, activate a source, or parse jobs.
It only extracts URL-shaped evidence from HTML attributes and same-origin JavaScript
bundles so F2 can learn recurring dynamic portal structures before introducing a
parser-family capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlparse, urlunparse

MAX_HTML_URLS = 96
MAX_SCRIPT_SOURCES = 8
MAX_SCRIPT_LITERALS = 96
MAX_LITERAL_LENGTH = 320

_ROUTE_MARKERS = (
    "api",
    "career",
    "careers",
    "job",
    "jobs",
    "openjob",
    "opening",
    "position",
    "positions",
    "posting",
    "recruit",
    "stellen",
    "vacanc",
    "graphql",
)
_QUOTED_LITERAL = re.compile(r"(?P<quote>['\"])(?P<value>[^'\"\r\n]{3,320})(?P=quote)")


@dataclass(frozen=True)
class HtmlDynamicSurfaceEvidence:
    script_sources: tuple[str, ...]
    url_attributes: tuple[str, ...]


@dataclass(frozen=True)
class DynamicRouteLiteral:
    raw: str
    normalized_url: str | None
    host: str | None
    markers: tuple[str, ...]


class _DynamicHtmlParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.script_sources: list[str] = []
        self.url_attributes: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.casefold()
        for key, raw_value in attrs:
            name = str(key or "").casefold()
            value = str(raw_value or "").strip()
            if not value:
                continue
            if tag_name == "script" and name == "src":
                self.script_sources.append(urljoin(self.base_url, value))
            if name in {"href", "src", "action"} or name.startswith("data-"):
                lowered = value.casefold()
                if (
                    value.startswith(("/", "./", "../", "http://", "https://"))
                    and any(marker in lowered for marker in _ROUTE_MARKERS)
                ):
                    self.url_attributes.append(urljoin(self.base_url, value))


def _normalize_http_url(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.casefold().strip(".")
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or "/"
    return urlunparse((parsed.scheme.casefold(), host + port, path, "", parsed.query, ""))


def extract_html_dynamic_surface_evidence(
    *,
    html: str,
    base_url: str,
    max_script_sources: int = MAX_SCRIPT_SOURCES,
    max_urls: int = MAX_HTML_URLS,
) -> HtmlDynamicSurfaceEvidence:
    parser = _DynamicHtmlParser(base_url)
    try:
        parser.feed(html or "")
    except Exception:
        return HtmlDynamicSurfaceEvidence((), ())

    scripts: list[str] = []
    for value in parser.script_sources:
        normalized = _normalize_http_url(value)
        if normalized and normalized not in scripts:
            scripts.append(normalized)
        if len(scripts) >= max(1, max_script_sources):
            break

    urls: list[str] = []
    for value in parser.url_attributes:
        normalized = _normalize_http_url(value)
        if normalized and normalized not in urls:
            urls.append(normalized)
        if len(urls) >= max(1, max_urls):
            break

    return HtmlDynamicSurfaceEvidence(tuple(scripts), tuple(urls))


def _route_markers(value: str) -> tuple[str, ...]:
    lowered = value.casefold()
    return tuple(marker for marker in _ROUTE_MARKERS if marker in lowered)


def _literal_to_url(raw: str, *, base_url: str) -> str | None:
    value = raw.strip()
    if not value or len(value) > MAX_LITERAL_LENGTH:
        return None
    if value.startswith(("http://", "https://")):
        return _normalize_http_url(value)
    if value.startswith(("/", "./", "../")):
        return _normalize_http_url(urljoin(base_url, value))
    return None


def extract_dynamic_route_literals(
    *,
    text: str,
    base_url: str,
    max_literals: int = MAX_SCRIPT_LITERALS,
) -> tuple[DynamicRouteLiteral, ...]:
    """Return bounded URL/route literals carrying job/API vocabulary.

    Arbitrary prose/provider-name scanning is intentionally excluded. A literal
    must be quoted, short, URL/path-shaped, and contain at least one route marker.
    """

    result: list[DynamicRouteLiteral] = []
    seen: set[tuple[str, str | None]] = set()
    for match in _QUOTED_LITERAL.finditer(text or ""):
        raw = match.group("value").strip()
        markers = _route_markers(raw)
        if not markers:
            continue
        normalized = _literal_to_url(raw, base_url=base_url)
        if normalized is None:
            continue
        parsed = urlparse(normalized)
        key = (raw, normalized)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            DynamicRouteLiteral(
                raw=raw,
                normalized_url=normalized,
                host=(parsed.hostname or "").casefold() or None,
                markers=markers,
            )
        )
        if len(result) >= max(1, max_literals):
            break
    return tuple(result)


def exact_host(url: str) -> str:
    return (urlparse(url).hostname or "").casefold().strip(".")


def same_host(left: str, right: str) -> bool:
    host = exact_host(left)
    return bool(host and host == exact_host(right))


__all__ = [
    "DynamicRouteLiteral",
    "HtmlDynamicSurfaceEvidence",
    "exact_host",
    "extract_dynamic_route_literals",
    "extract_html_dynamic_surface_evidence",
    "same_host",
]
