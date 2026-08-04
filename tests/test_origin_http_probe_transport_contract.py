from __future__ import annotations

from typing import Any

import requests

from scripts import run_origin_source_discovery_agent as origin_runtime
from src.search_intelligence.origin_http_probe_transport_contract import (
    ORIGIN_HTTP_PROBE_HEADERS,
    install_origin_http_probe_transport_contract,
)


def test_browser_compatible_probe_keeps_one_normal_gated_request(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    install_origin_http_probe_transport_contract()
    calls: list[dict[str, Any]] = []

    class Response:
        status_code = 200
        url = (
            "https://www.eon.com/de/ueber-uns/karriere/"
            "unsere-gesellschaften/digital-technology.html"
        )
        text = "<html><title>E.ON Digital Technology Karriere</title></html>"
        content = text.encode("utf-8")

    def fake_get(url: str, **kwargs: Any) -> Response:
        calls.append({"url": url, **kwargs})
        return Response()

    monkeypatch.setattr(requests, "get", fake_get)

    result = origin_runtime.http_probe(Response.url, timeout_seconds=6.0)

    assert len(calls) == 1
    assert calls[0]["allow_redirects"] is True
    assert calls[0]["timeout"] == 6.0
    assert calls[0]["headers"] == ORIGIN_HTTP_PROBE_HEADERS
    assert str(ORIGIN_HTTP_PROBE_HEADERS["User-Agent"]).startswith("Mozilla/5.0")
    assert ORIGIN_HTTP_PROBE_HEADERS["Accept-Language"].startswith("de-DE")
    assert result.reachable is True
    assert result.career_like is True
    assert result.status_code == 200


def test_transport_failure_is_not_retried(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    install_origin_http_probe_transport_contract()
    attempts = 0

    def fail_once(*args: Any, **kwargs: Any) -> None:
        nonlocal attempts
        attempts += 1
        raise requests.Timeout("bounded probe timeout")

    monkeypatch.setattr(requests, "get", fail_once)

    result = origin_runtime.http_probe(
        "https://www.eon.com/de/ueber-uns/karriere/",
        timeout_seconds=6.0,
    )

    assert attempts == 1
    assert result.reachable is False
    assert result.status_code is None
    assert result.reason == "request failed: Timeout"
