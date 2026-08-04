from __future__ import annotations

from typing import Any

import requests

from scripts import run_origin_source_discovery_agent as origin_runtime
from src.search_intelligence.origin_bounded_head_verification_contract import (
    HEAD_VERIFICATION_HEADERS,
    probe_with_bounded_head_verification,
)


EON_URL = (
    "https://www.eon.com/de/ueber-uns/karriere/"
    "unsere-gesellschaften/digital-technology.html"
)


def _probe(
    *,
    status_code: int,
    reachable: bool,
    career_like: bool = True,
) -> origin_runtime.OriginDiscoveryProbeResult:
    return origin_runtime.OriginDiscoveryProbeResult(
        url=EON_URL,
        final_url=EON_URL,
        status_code=status_code,
        reachable=reachable,
        career_like=career_like,
        reason=f"status={status_code}; career_like={career_like}",
    )


def test_successful_get_never_opens_head(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def unexpected_head(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("HEAD must stay closed after a successful GET")

    monkeypatch.setattr(requests, "head", unexpected_head)

    result = probe_with_bounded_head_verification(
        lambda url, *, timeout_seconds: _probe(status_code=200, reachable=True),
        EON_URL,
        timeout_seconds=6.0,
    )

    assert result.reachable is True
    assert result.status_code == 200


def test_get_403_can_open_one_independent_head_verification(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    calls: list[dict[str, Any]] = []

    class Response:
        status_code = 200
        url = EON_URL
        text = ""
        content = b""

    def fake_head(url: str, **kwargs: Any) -> Response:
        calls.append({"url": url, **kwargs})
        return Response()

    monkeypatch.setattr(requests, "head", fake_head)

    result = probe_with_bounded_head_verification(
        lambda url, *, timeout_seconds: _probe(status_code=403, reachable=False),
        EON_URL,
        timeout_seconds=6.0,
    )

    assert len(calls) == 1
    assert calls[0]["url"] == EON_URL
    assert calls[0]["allow_redirects"] is True
    assert calls[0]["timeout"] == 6.0
    assert calls[0]["headers"] == HEAD_VERIFICATION_HEADERS
    assert result.reachable is True
    assert result.status_code == 200
    assert result.career_like is True
    assert "GET status=403" in result.reason


def test_failed_head_does_not_promote_get_error(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    attempts = 0

    class Response:
        status_code = 403
        url = EON_URL
        text = ""
        content = b""

    def rejected_head(*args: Any, **kwargs: Any) -> Response:
        nonlocal attempts
        attempts += 1
        return Response()

    monkeypatch.setattr(requests, "head", rejected_head)

    result = probe_with_bounded_head_verification(
        lambda url, *, timeout_seconds: _probe(status_code=403, reachable=False),
        EON_URL,
        timeout_seconds=6.0,
    )

    assert attempts == 1
    assert result.reachable is False
    assert result.status_code == 403
    assert "HEAD verification rejected" in result.reason


def test_non_method_failure_never_opens_head(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    def unexpected_head(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("HEAD must stay closed for non-eligible failures")

    monkeypatch.setattr(requests, "head", unexpected_head)

    result = probe_with_bounded_head_verification(
        lambda url, *, timeout_seconds: origin_runtime.OriginDiscoveryProbeResult(
            url=url,
            final_url=None,
            status_code=None,
            reachable=False,
            career_like=False,
            reason="request failed: Timeout",
        ),
        EON_URL,
        timeout_seconds=6.0,
    )

    assert result.reachable is False
    assert result.status_code is None
    assert result.reason == "request failed: Timeout"
