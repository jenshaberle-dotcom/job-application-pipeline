from __future__ import annotations

from dataclasses import dataclass

import requests

from src.search_intelligence.public_web_search import (
    BACKEND_POLICIES,
    DEFAULT_SEARCH_BACKEND,
    backend_available,
    search_public_web,
)


@dataclass
class _FakeResponse:
    text: str = ""
    url: str = "https://html.duckduckgo.com/html/"
    status_code: int = 200
    payload: object | None = None

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self) -> object:
        if self.payload is None:
            raise ValueError("no json")
        return self.payload


def test_default_backend_is_zero_key_and_not_paid() -> None:
    assert DEFAULT_SEARCH_BACKEND == "bing_rss"
    policy = BACKEND_POLICIES[DEFAULT_SEARCH_BACKEND]
    assert policy.requires_secret is False
    assert policy.paid_external_tool is False
    assert policy.automatic_fallback_allowed is False


def test_duckduckgo_html_extracts_generic_result_without_platform_logic() -> None:
    html = """
    <html><body>
      <a class="result__a"
         href="/l/?uddg=https%3A%2F%2Fwww.linkedin.com%2Fjobs%2Fview%2F123456%2F">
         HDI Group sucht AI Architect
      </a>
      <a class="result__a"
         href="/l/?uddg=https%3A%2F%2Fexample.com%2Fcareers%2Fdata">
         Example careers
      </a>
    </body></html>
    """

    calls: list[str] = []

    def request_get(url: str, **_: object) -> _FakeResponse:
        calls.append(url)
        return _FakeResponse(text=html, url=url)

    result = search_public_web(
        provider="duckduckgo_html",
        query='site:linkedin.com/jobs/view "AI Architect" "Hannover"',
        max_results=5,
        timeout_seconds=2.0,
        request_get=request_get,
    )

    assert result.status == "ok"
    assert result.request_count == 1
    assert len(calls) == 1
    assert [item.url for item in result.results] == [
        "https://www.linkedin.com/jobs/view/123456/",
        "https://example.com/careers/data",
    ]
    assert result.results[0].title == "HDI Group sucht AI Architect"
    assert result.results[0].snippet == ""
    assert result.results[0].provider == "duckduckgo_html"


def test_default_backend_failure_never_calls_paid_backend() -> None:
    post_calls = 0

    def request_get(*_: object, **__: object) -> _FakeResponse:
        raise requests.ConnectionError("offline")

    def request_post(*_: object, **__: object) -> _FakeResponse:
        nonlocal post_calls
        post_calls += 1
        return _FakeResponse(payload={"results": []})

    result = search_public_web(
        provider="duckduckgo_html",
        query="bounded query",
        max_results=5,
        timeout_seconds=1.0,
        request_get=request_get,
        request_post=request_post,
    )

    assert result.status == "transport_error"
    assert result.request_count == 1
    assert result.results == ()
    assert post_calls == 0


def test_tavily_is_explicit_optional_backend(monkeypatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    assert backend_available("duckduckgo_html") is True
    assert backend_available("tavily") is False
    assert BACKEND_POLICIES["tavily"].requires_secret is True
    assert BACKEND_POLICIES["tavily"].paid_external_tool is True
    assert BACKEND_POLICIES["tavily"].automatic_fallback_allowed is False

    result = search_public_web(
        provider="tavily",
        query="bounded query",
        max_results=5,
        timeout_seconds=1.0,
    )
    assert result.status == "provider_unavailable"
    assert result.request_count == 0
    assert result.results == ()


def test_duckduckgo_http_202_empty_page_is_block_signal_not_zero_yield() -> None:
    def request_get(url: str, **_: object) -> _FakeResponse:
        return _FakeResponse(
            text="<html><body><form id=\"challenge-form\"></form></body></html>",
            url=url,
            status_code=202,
        )

    result = search_public_web(
        provider="duckduckgo_html",
        query="bounded query",
        max_results=5,
        timeout_seconds=1.0,
        request_get=request_get,
    )

    assert result.status == "blocked_or_challenge"
    assert result.request_count == 1
    assert result.results == ()
    assert result.error_type == "http_202"


def test_bing_rss_parses_keyless_structured_results() -> None:
    rss = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0"><channel>
      <item>
        <title>HDI Group sucht AI Architect in Hannover | LinkedIn</title>
        <link>https://de.linkedin.com/jobs/view/ai-architect-at-hdi-group-123456</link>
        <description>HDI Group Hannover</description>
      </item>
      <item>
        <title>Example careers</title>
        <link>https://example.com/careers</link>
        <description>Example</description>
      </item>
    </channel></rss>"""

    calls: list[str] = []

    def request_get(url: str, **_: object) -> _FakeResponse:
        calls.append(url)
        return _FakeResponse(text=rss, url=url)

    result = search_public_web(
        provider="bing_rss",
        query='site:linkedin.com/jobs/view "AI Architect" "Hannover"',
        max_results=5,
        timeout_seconds=2.0,
        request_get=request_get,
    )

    assert result.status == "ok"
    assert result.request_count == 1
    assert len(calls) == 1
    assert "format=rss" in calls[0]
    assert result.results[0].provider == "bing_rss"
    assert result.results[0].url.startswith("https://de.linkedin.com/jobs/view/")
    assert result.results[0].title.startswith("HDI Group sucht AI Architect")
    assert result.results[0].snippet == "HDI Group Hannover"


def test_searxng_json_is_zero_paid_and_requires_explicit_runtime_endpoint(monkeypatch) -> None:
    monkeypatch.delenv("SEARXNG_BASE_URL", raising=False)
    assert BACKEND_POLICIES["searxng_json"].paid_external_tool is False
    assert BACKEND_POLICIES["searxng_json"].automatic_fallback_allowed is False
    assert backend_available("searxng_json") is False
    result = search_public_web(provider="searxng_json", query="bounded query", max_results=5, timeout_seconds=1.0)
    assert result.status == "provider_unavailable"
    assert result.request_count == 0


def test_searxng_json_parses_generic_results(monkeypatch) -> None:
    monkeypatch.setenv("SEARXNG_BASE_URL", "http://127.0.0.1:8080")
    calls = []
    def request_get(url: str, **kwargs: object) -> _FakeResponse:
        calls.append((url, kwargs))
        return _FakeResponse(payload={"results": [{"url": "https://www.linkedin.com/jobs/view/123456/", "title": "AI Architect", "content": "Example"}]})
    result = search_public_web(provider="searxng_json", query="site:linkedin.com AI Architect Hannover", max_results=5, timeout_seconds=2.0, request_get=request_get)
    assert result.status == "ok"
    assert result.request_count == 1
    assert result.results[0].provider == "searxng_json"
    assert result.results[0].url == "https://www.linkedin.com/jobs/view/123456/"
    assert calls[0][0] == "http://127.0.0.1:8080/search"
    assert calls[0][1]["params"]["format"] == "json"
