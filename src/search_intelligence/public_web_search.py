"""Replaceable, bounded web-search backends for discovery-only evidence.

The contract deliberately separates *search intent* from *transport*. Product
logic must not depend on a paid provider. A backend may fail or return zero
results without blocking the wider JAP pipeline.

The default backend is Bing's keyless RSS result surface: structured XML, no
account/API key and no paid plan. DuckDuckGo HTML remains a diagnostic/free
adapter but is not default because current automated-client blocking can produce
empty/challenge responses. Tavily remains explicit optional residual/benchmark
only; there is no automatic paid fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import os
from typing import Callable, Mapping
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

import requests

from src.search_intelligence.multi_origin_evidence import (
    decode_search_redirect_url,
    normalize_url,
)


DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"
BING_RSS_URL = "https://www.bing.com/search"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_SEARCH_BACKEND = "bing_rss"
SUPPORTED_SEARCH_BACKENDS = ("duckduckgo_html", "bing_rss", "tavily")


@dataclass(frozen=True)
class SearchBackendPolicy:
    name: str
    requires_secret: bool
    paid_external_tool: bool
    automatic_fallback_allowed: bool = False


BACKEND_POLICIES: Mapping[str, SearchBackendPolicy] = {
    "duckduckgo_html": SearchBackendPolicy(
        name="duckduckgo_html",
        requires_secret=False,
        paid_external_tool=False,
    ),
    "bing_rss": SearchBackendPolicy(
        name="bing_rss",
        requires_secret=False,
        paid_external_tool=False,
    ),
    "tavily": SearchBackendPolicy(
        name="tavily",
        requires_secret=True,
        paid_external_tool=True,
    ),
}


@dataclass(frozen=True)
class PublicSearchResult:
    provider: str
    query: str
    url: str
    title: str = ""
    snippet: str = ""
    transport_link_kind: str = "direct"


@dataclass(frozen=True)
class PublicSearchResponse:
    provider: str
    query: str
    status: str
    results: tuple[PublicSearchResult, ...]
    request_count: int
    error_type: str | None = None


class _DuckDuckGoResultParser(HTMLParser):
    """Extract only result-title anchors from the bounded HTML result page."""

    def __init__(self) -> None:
        super().__init__()
        self._href: str | None = None
        self._text: list[str] = []
        self.rows: list[tuple[str, str]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "a":
            return
        values = dict(attrs)
        class_tokens = {
            token.casefold()
            for token in str(values.get("class") or "").split()
            if token
        }
        href = str(values.get("href") or "").strip()
        if "result__a" not in class_tokens or not href:
            return
        self._href = href
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        title = " ".join(" ".join(self._text).split())
        self.rows.append((self._href, title))
        self._href = None
        self._text = []


def _transport_link_kind(
    *,
    raw_url: str,
    decoded_url: str,
    backend_host_suffix: str,
    redirect_path_prefix: str,
    base_url: str | None = None,
) -> str:
    normalized_raw = normalize_url(raw_url, base_url=base_url)
    if not normalized_raw:
        return "invalid"
    parsed = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(normalized_raw)
    raw_host = (parsed.hostname or "").casefold().strip(".")
    is_backend_redirect = (
        (raw_host == backend_host_suffix or raw_host.endswith("." + backend_host_suffix))
        and parsed.path.casefold().startswith(redirect_path_prefix)
    )
    if not is_backend_redirect:
        return "direct"
    return "redirect_unwrapped" if decoded_url != normalized_raw else "redirect_unresolved"


def _missing_or_placeholder_secret(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip()
    lowered = normalized.casefold()
    return (
        not normalized
        or normalized == "..."
        or normalized in {"<YOUR_API_KEY>", "YOUR_API_KEY", "changeme"}
        or "your_api_key" in lowered
        or "realer_key" in lowered
    )


def backend_available(provider: str) -> bool:
    if provider not in SUPPORTED_SEARCH_BACKENDS:
        return False
    if provider == "tavily":
        return not _missing_or_placeholder_secret(os.getenv("TAVILY_API_KEY"))
    return True


def _duckduckgo_html_search(
    query: str,
    *,
    max_results: int,
    timeout_seconds: float,
    request_get: Callable[..., requests.Response],
) -> PublicSearchResponse:
    url = DUCKDUCKGO_HTML_URL + "?" + urlencode({"q": query})
    try:
        response = request_get(
            url,
            headers={
                "User-Agent": (
                    "job-application-pipeline-public-search/0.1 "
                    "(bounded; discovery-only; no browser automation)"
                ),
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return PublicSearchResponse(
            provider="duckduckgo_html",
            query=query,
            status="transport_error",
            results=(),
            request_count=1,
            error_type=type(exc).__name__,
        )

    parser = _DuckDuckGoResultParser()
    parser.feed(response.text or "")

    results: list[PublicSearchResult] = []
    seen: set[str] = set()
    for raw_url, title in parser.rows:
        decoded = decode_search_redirect_url(raw_url, base_url=str(response.url))
        if not decoded or decoded in seen:
            continue
        seen.add(decoded)
        results.append(
            PublicSearchResult(
                provider="duckduckgo_html",
                query=query,
                url=decoded,
                title=title,
                snippet="",
                transport_link_kind=_transport_link_kind(
                    raw_url=raw_url,
                    decoded_url=decoded,
                    backend_host_suffix="duckduckgo.com",
                    redirect_path_prefix="/l/",
                    base_url=str(response.url),
                ),
            )
        )
        if len(results) >= max_results:
            break

    if not results and (
        response.status_code == 202
        or "challenge-form" in (response.text or "").casefold()
        or "anomaly" in (response.text or "").casefold()
    ):
        return PublicSearchResponse(
            provider="duckduckgo_html",
            query=query,
            status="blocked_or_challenge",
            results=(),
            request_count=1,
            error_type=f"http_{response.status_code}",
        )

    return PublicSearchResponse(
        provider="duckduckgo_html",
        query=query,
        status="ok" if results else "zero_yield",
        results=tuple(results),
        request_count=1,
    )


def _bing_rss_search(
    query: str,
    *,
    max_results: int,
    timeout_seconds: float,
    request_get: Callable[..., requests.Response],
) -> PublicSearchResponse:
    url = BING_RSS_URL + "?" + urlencode(
        {
            "q": query,
            "format": "rss",
            "count": max(1, min(max_results, 10)),
        }
    )
    try:
        response = request_get(
            url,
            headers={
                "User-Agent": (
                    "job-application-pipeline-public-search/0.1 "
                    "(bounded; discovery-only; RSS client)"
                ),
                "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.1",
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return PublicSearchResponse(
            provider="bing_rss",
            query=query,
            status="transport_error",
            results=(),
            request_count=1,
            error_type=type(exc).__name__,
        )

    try:
        root = ET.fromstring(response.text or "")
    except ET.ParseError:
        return PublicSearchResponse(
            provider="bing_rss",
            query=query,
            status="invalid_response",
            results=(),
            request_count=1,
            error_type="xml_parse_error",
        )

    results: list[PublicSearchResult] = []
    seen: set[str] = set()
    for item in root.findall(".//item"):
        raw_url = " ".join(str(item.findtext("link") or "").split()).strip()
        url_value = decode_search_redirect_url(raw_url)
        if not url_value or url_value in seen:
            continue
        seen.add(url_value)
        results.append(
            PublicSearchResult(
                provider="bing_rss",
                query=query,
                url=url_value,
                title=" ".join(str(item.findtext("title") or "").split()),
                snippet=" ".join(str(item.findtext("description") or "").split()),
                transport_link_kind=_transport_link_kind(
                    raw_url=raw_url,
                    decoded_url=url_value,
                    backend_host_suffix="bing.com",
                    redirect_path_prefix="/ck/",
                ),
            )
        )
        if len(results) >= max_results:
            break

    return PublicSearchResponse(
        provider="bing_rss",
        query=query,
        status="ok" if results else "zero_yield",
        results=tuple(results),
        request_count=1,
    )


def _tavily_search(
    query: str,
    *,
    max_results: int,
    timeout_seconds: float,
    request_post: Callable[..., requests.Response],
) -> PublicSearchResponse:
    api_key = os.getenv("TAVILY_API_KEY")
    if _missing_or_placeholder_secret(api_key):
        return PublicSearchResponse(
            provider="tavily",
            query=query,
            status="provider_unavailable",
            results=(),
            request_count=0,
            error_type="missing_api_key",
        )

    try:
        response = request_post(
            TAVILY_SEARCH_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "search_depth": "basic",
                "max_results": max(1, min(max_results, 10)),
                "include_answer": False,
                "include_raw_content": False,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return PublicSearchResponse(
            provider="tavily",
            query=query,
            status="transport_error",
            results=(),
            request_count=1,
            error_type=type(exc).__name__,
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    rows = payload.get("results", []) if isinstance(payload, dict) else []
    results: list[PublicSearchResult] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        results.append(
            PublicSearchResult(
                provider="tavily",
                query=query,
                url=url,
                title=str(item.get("title") or ""),
                snippet=str(item.get("content") or ""),
            )
        )
        if len(results) >= max_results:
            break

    return PublicSearchResponse(
        provider="tavily",
        query=query,
        status="ok" if results else "zero_yield",
        results=tuple(results),
        request_count=1,
    )


def search_public_web(
    *,
    provider: str,
    query: str,
    max_results: int,
    timeout_seconds: float,
    request_get: Callable[..., requests.Response] = requests.get,
    request_post: Callable[..., requests.Response] = requests.post,
) -> PublicSearchResponse:
    """Execute exactly one explicitly selected backend.

    No implicit provider fallback is permitted. In particular, failure of the
    free/default backend never authorizes a paid-provider call.
    """

    if provider not in SUPPORTED_SEARCH_BACKENDS:
        raise ValueError(f"Unsupported public search backend: {provider}")

    if provider == "duckduckgo_html":
        return _duckduckgo_html_search(
            query,
            max_results=max_results,
            timeout_seconds=timeout_seconds,
            request_get=request_get,
        )
    if provider == "bing_rss":
        return _bing_rss_search(
            query,
            max_results=max_results,
            timeout_seconds=timeout_seconds,
            request_get=request_get,
        )
    return _tavily_search(
        query,
        max_results=max_results,
        timeout_seconds=timeout_seconds,
        request_post=request_post,
    )
