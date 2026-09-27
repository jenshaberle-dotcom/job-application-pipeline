"""Provider-agnostic public web-search transport primitives.

This module intentionally contains no LinkedIn/Indeed semantics. Market sensors
supply site-bounded queries and validate returned hosts/paths separately.

The default backend is DuckDuckGo's non-JavaScript HTML search surface because it
requires no API key, account, paid subscription, browser automation, or provider
SDK. It is best-effort only: blocking/markup drift is a valid unavailable outcome
and must never trigger an automatic paid-provider fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urlencode, urlparse

import requests

from src.search_intelligence.multi_origin_evidence import decode_search_redirect_url


DUCKDUCKGO_HTML_SEARCH_URL = "https://html.duckduckgo.com/html/"
DEFAULT_USER_AGENT = (
    "job-application-pipeline-public-search/0.1 "
    "(bounded; no browser automation; no raw html persistence)"
)


@dataclass(frozen=True)
class PublicSearchResult:
    url: str
    title: str
    snippet: str
    query: str
    provider: str


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._href: str | None = None
        self._text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        self._href = href
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        title = " ".join(" ".join(self._text).split()).strip()
        self.links.append((self._href, title))
        self._href = None
        self._text = []


def parse_duckduckgo_html_results(
    html: str,
    *,
    query: str,
    base_url: str = DUCKDUCKGO_HTML_SEARCH_URL,
    max_results: int = 10,
) -> tuple[PublicSearchResult, ...]:
    """Extract outbound result links without depending on DDG CSS selectors."""

    parser = _AnchorParser()
    parser.feed(html or "")

    result: list[PublicSearchResult] = []
    seen: set[str] = set()
    for raw_url, title in parser.links:
        decoded = decode_search_redirect_url(raw_url, base_url=base_url)
        if not decoded:
            continue
        parsed = urlparse(decoded)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        if parsed.netloc.casefold().endswith("duckduckgo.com"):
            continue
        if decoded in seen:
            continue
        seen.add(decoded)
        result.append(
            PublicSearchResult(
                url=decoded,
                title=title,
                snippet="",
                query=query,
                provider="duckduckgo_html",
            )
        )
        if len(result) >= max(1, max_results):
            break
    return tuple(result)


def duckduckgo_html_search(
    query: str,
    *,
    max_results: int,
    timeout_seconds: float,
) -> tuple[PublicSearchResult, ...]:
    """Run one bounded keyless search request and return link-level evidence."""

    url = DUCKDUCKGO_HTML_SEARCH_URL + "?" + urlencode({"q": query})
    response = requests.get(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return parse_duckduckgo_html_results(
        response.text,
        query=query,
        base_url=response.url,
        max_results=max_results,
    )


def deduplicate_public_results(
    values: Iterable[PublicSearchResult],
) -> tuple[PublicSearchResult, ...]:
    result: list[PublicSearchResult] = []
    seen: set[tuple[str, str]] = set()
    for item in values:
        key = (item.provider, item.url)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return tuple(result)
