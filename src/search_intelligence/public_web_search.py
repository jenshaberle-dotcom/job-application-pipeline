"""Replaceable, bounded web-search backend contract for discovery-only evidence.

Market-sensor search is intentionally non-authoritative and optional. No external
provider is required by default. A provider is used only when explicitly selected
by an operator/configuration authority.

The currently admitted real adapter is Tavily because it already produced a
bounded successful proof. It remains a residual optional capability: missing
credentials, quota or provider availability must never block unrelated JAP paths.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Callable, Mapping

import requests


TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_SEARCH_BACKEND = "none"
SUPPORTED_SEARCH_BACKENDS = ("tavily",)


@dataclass(frozen=True)
class SearchBackendPolicy:
    name: str
    requires_secret: bool
    paid_external_tool: bool
    automatic_fallback_allowed: bool = False


BACKEND_POLICIES: Mapping[str, SearchBackendPolicy] = {
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
    return False


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
    request_post: Callable[..., requests.Response] = requests.post,
) -> PublicSearchResponse:
    """Execute exactly one explicitly selected admitted backend.

    There is no implicit provider selection and no automatic fallback. The
    default market-sensor mode is handled by the caller as provider=none and
    performs zero external requests.
    """

    if provider not in SUPPORTED_SEARCH_BACKENDS:
        raise ValueError(f"Unsupported public search backend: {provider}")

    if provider == "tavily":
        return _tavily_search(
            query,
            max_results=max_results,
            timeout_seconds=timeout_seconds,
            request_post=request_post,
        )

    raise AssertionError(f"Unreachable provider dispatch: {provider}")
