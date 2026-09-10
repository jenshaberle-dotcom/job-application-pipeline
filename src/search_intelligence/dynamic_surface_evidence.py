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
MAX_SCRIPT_SOURCES = 24
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
_APP_SCRIPT_MARKERS = ("main", "app", "bundle", "career", "job", "position", "vacanc", "recruit")
_LOW_VALUE_SCRIPT_MARKERS = ("jquery", "editor", "richtext", "cookie", "analytics", "swiper", "aos")
_STATIC_SUFFIXES = (
    ".css",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
    ".woff",
    ".woff2",
    ".pdf",
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
    try:
        parsed_port = parsed.port
    except ValueError:
        return None
    port = f":{parsed_port}" if parsed_port else ""
    path = parsed.path or "/"
    return urlunparse((parsed.scheme.casefold(), host + port, path, "", parsed.query, ""))


def _script_priority(url: str) -> tuple[int, int, str]:
    parsed = urlparse(url)
    path_query = f"{parsed.path}?{parsed.query}".casefold()
    app_hits = sum(marker in path_query for marker in _APP_SCRIPT_MARKERS)
    low_hits = sum(marker in path_query for marker in _LOW_VALUE_SCRIPT_MARKERS)
    return (-app_hits, low_hits, path_query)


def prioritize_script_sources(
    values: tuple[str, ...] | list[str],
    *,
    max_scripts: int,
) -> tuple[str, ...]:
    unique: list[str] = []
    for value in values:
        normalized = _normalize_http_url(value)
        if normalized and normalized not in unique:
            unique.append(normalized)
    ordered = sorted(unique, key=_script_priority)
    return tuple(ordered[: max(1, max_scripts)])


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

    scripts = prioritize_script_sources(
        parser.script_sources,
        max_scripts=max_script_sources,
    )

    urls: list[str] = []
    for value in parser.url_attributes:
        normalized = _normalize_http_url(value)
        if normalized and normalized not in urls:
            urls.append(normalized)
        if len(urls) >= max(1, max_urls):
            break

    return HtmlDynamicSurfaceEvidence(scripts, tuple(urls))


def _route_markers(value: str, *, normalized_url: str | None = None) -> tuple[str, ...]:
    raw = value.casefold()
    parsed = urlparse(normalized_url or value)
    path_query = f"{parsed.path}?{parsed.query}".casefold()
    path_markers = tuple(marker for marker in _ROUTE_MARKERS if marker in path_query)
    if path_markers:
        return path_markers

    # A jobs/careers hostname may itself be useful evidence, but do not let it
    # turn every static asset on that host into a dynamic route candidate.
    if parsed.path.casefold().endswith(_STATIC_SUFFIXES):
        return ()
    host = (parsed.hostname or "").casefold()
    return tuple(marker for marker in _ROUTE_MARKERS if marker in host or marker in raw)


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
        normalized = _literal_to_url(raw, base_url=base_url)
        if normalized is None:
            continue
        markers = _route_markers(raw, normalized_url=normalized)
        if not markers:
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
    "prioritize_script_sources",
    "same_host",
]
