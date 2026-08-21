"""Strict deterministic navigation for employer pages backed by explicit job-link APIs.

The functions in this module perform no network I/O. They only turn already
fetched employer HTML, one explicitly referenced same-host application script,
and one explicitly named same-host job-link API response into bounded navigation
candidates. No provider name, company mapping, guessed endpoint, or persistence is
used here.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from src.search_intelligence.multi_origin_evidence import job_detail_url_shape


_LINK_INVENTORY_ROUTE = re.compile(
    r"/(?:api|rest|services?)(?:/[^\s\"'<>?]*)*/(?:"
    r"job[-_]?links?|job[-_]?urls?|vacanc(?:y|ies)[-_]?links?|"
    r"position[-_]?links?|requisition[-_]?links?|opening[-_]?links?"
    r")(?:/|(?=[?\"'\s<]))",
    flags=re.IGNORECASE,
)
_APPLICATION_BASENAME = re.compile(r"^(?:main|app)(?:[._-]|$)", flags=re.IGNORECASE)
_REJECT_SCRIPT_MARKERS = (
    "jquery",
    "bootstrap",
    "swiper",
    "shareon",
    "analytics",
    "tracking",
    "cookie",
    "consent",
    "recaptcha",
    "polyfill",
    "webpack",
    "runtime",
    "vendor",
)


def _host(value: str) -> str:
    return (urlparse(str(value or "")).hostname or "").casefold().strip(".")


def _allowed_host(url: str, allowed_hosts: tuple[str, ...] | set[str]) -> bool:
    allowed = {str(item).casefold().strip(".") for item in allowed_hosts if str(item)}
    return bool(_host(url) and _host(url) in allowed)


class _ScriptSourceParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "script":
            return
        source = dict(attrs).get("src")
        if not source:
            return
        self.sources.append(urljoin(self.base_url, source.strip()))


def strict_same_host_application_script_url(
    *,
    page_url: str,
    html: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> str | None:
    """Return one unambiguous same-host application script, otherwise ``None``.

    This is intentionally narrower than generic static-asset discovery. Only
    HTTPS JavaScript whose basename is ``main...`` or ``app...`` qualifies, and
    common framework/library assets are rejected. Multiple qualifying scripts are
    ambiguous and therefore create no navigation authority.
    """

    parser = _ScriptSourceParser(page_url)
    parser.feed(html or "")
    candidates: list[str] = []
    seen: set[str] = set()
    for source in parser.sources:
        parsed = urlparse(source)
        if parsed.scheme.casefold() != "https" or not parsed.hostname:
            continue
        if not _allowed_host(source, allowed_hosts):
            continue
        path = parsed.path or ""
        lowered = path.casefold()
        if not lowered.endswith(".js") or any(marker in lowered for marker in _REJECT_SCRIPT_MARKERS):
            continue
        basename = path.rsplit("/", 1)[-1]
        if not _APPLICATION_BASENAME.search(basename):
            continue
        clean = parsed._replace(query="", fragment="").geturl()
        if clean in seen:
            continue
        seen.add(clean)
        candidates.append(clean)
    if len(candidates) != 1:
        return None
    return candidates[0]


def explicit_same_host_job_link_inventory_url(
    *,
    asset_url: str,
    javascript: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> str | None:
    """Return one explicitly encoded same-host job-link inventory endpoint.

    Relative route literals are accepted only when the application script itself
    contains the route and the resolved target remains on an already-authorized
    host. Multiple distinct matching routes fail closed.
    """

    if not _allowed_host(asset_url, allowed_hosts):
        return None
    decoded = (javascript or "").replace(r"\/", "/").replace(r"\u002F", "/").replace(r"\u002f", "/")
    candidates: list[str] = []
    seen: set[str] = set()
    for match in _LINK_INVENTORY_ROUTE.finditer(decoded):
        route = match.group(0).rstrip("/")
        target = urljoin(asset_url, route)
        parsed = urlparse(target)
        if parsed.scheme.casefold() != "https" or not _allowed_host(target, allowed_hosts):
            continue
        clean = parsed._replace(query="", fragment="").geturl().rstrip("/")
        if clean in seen:
            continue
        seen.add(clean)
        candidates.append(clean)
    if len(candidates) != 1:
        return None
    return candidates[0]


def explicit_job_detail_urls_from_inventory(
    *,
    api_url: str,
    body: str,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = 8,
) -> tuple[str, ...]:
    """Extract bounded strict job-detail URLs from one JSON link inventory."""

    if limit < 1 or not _allowed_host(api_url, allowed_hosts):
        return ()
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return ()

    result: list[str] = []
    seen: set[str] = set()
    nodes = 0

    def walk(value: object, depth: int) -> None:
        nonlocal nodes
        if len(result) >= limit or nodes >= 50_000 or depth > 18:
            return
        nodes += 1
        if isinstance(value, dict):
            for child in value.values():
                walk(child, depth + 1)
            return
        if isinstance(value, list):
            for child in value[:5000]:
                walk(child, depth + 1)
            return
        if not isinstance(value, str):
            return
        text = value.strip().replace(r"\/", "/")
        if not (text.startswith("/") or text.startswith("https://")):
            return
        target = urljoin(api_url, text)
        parsed = urlparse(target)
        if parsed.scheme.casefold() != "https" or not _allowed_host(target, allowed_hosts):
            return
        clean = parsed._replace(query="", fragment="").geturl().rstrip("/")
        if clean in seen or not job_detail_url_shape(clean):
            return
        seen.add(clean)
        result.append(clean)

    walk(payload, 0)
    return tuple(result)


__all__ = [
    "explicit_job_detail_urls_from_inventory",
    "explicit_same_host_job_link_inventory_url",
    "strict_same_host_application_script_url",
]
