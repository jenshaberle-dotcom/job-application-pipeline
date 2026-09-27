from __future__ import annotations

from dataclasses import dataclass

import pytest
import requests

from src.search_intelligence.public_web_search import (
    BACKEND_POLICIES,
    DEFAULT_SEARCH_BACKEND,
    SUPPORTED_SEARCH_BACKENDS,
    backend_available,
    search_public_web,
)


@dataclass
class _FakeResponse:
    status_code: int = 200
    payload: object | None = None

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self) -> object:
        if self.payload is None:
            raise ValueError("no json")
        return self.payload


def test_default_market_search_backend_is_none() -> None:
    assert DEFAULT_SEARCH_BACKEND == "none"
    assert "none" not in BACKEND_POLICIES
    assert "duckduckgo_html" not in SUPPORTED_SEARCH_BACKENDS
    assert "bing_rss" not in SUPPORTED_SEARCH_BACKENDS
    assert SUPPORTED_SEARCH_BACKENDS == ("tavily",)


def test_tavily_is_explicit_optional_residual_backend(monkeypatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    assert backend_available("tavily") is False
    policy = BACKEND_POLICIES["tavily"]
    assert policy.requires_secret is True
    assert policy.paid_external_tool is True
    assert policy.automatic_fallback_allowed is False

    result = search_public_web(
        provider="tavily",
        query="bounded query",
        max_results=5,
        timeout_seconds=1.0,
    )
    assert result.status == "provider_unavailable"
    assert result.request_count == 0
    assert result.results == ()


def test_tavily_request_stays_basic_without_raw_content(monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    calls: list[dict[str, object]] = []

    def request_post(url: str, **kwargs: object) -> _FakeResponse:
        calls.append({"url": url, **kwargs})
        return _FakeResponse(
            payload={
                "results": [
                    {
                        "url": "https://www.linkedin.com/jobs/view/123456/",
                        "title": "HDI Group sucht AI Architect",
                        "content": "Bounded public search snippet",
                    }
                ]
            }
        )

    result = search_public_web(
        provider="tavily",
        query='"linkedin.com/jobs/view" "AI Architect" "Hannover" Germany',
        max_results=5,
        timeout_seconds=2.0,
        request_post=request_post,
    )

    assert result.status == "ok"
    assert result.request_count == 1
    assert len(result.results) == 1
    assert result.results[0].provider == "tavily"
    assert result.results[0].transport_link_kind == "direct"

    assert len(calls) == 1
    payload = calls[0]["json"]
    assert isinstance(payload, dict)
    assert payload["search_depth"] == "basic"
    assert payload["include_answer"] is False
    assert payload["include_raw_content"] is False


def test_removed_free_backends_are_not_silently_callable() -> None:
    for provider in ("duckduckgo_html", "bing_rss"):
        with pytest.raises(ValueError, match="Unsupported public search backend"):
            search_public_web(
                provider=provider,
                query="bounded query",
                max_results=5,
                timeout_seconds=1.0,
            )
