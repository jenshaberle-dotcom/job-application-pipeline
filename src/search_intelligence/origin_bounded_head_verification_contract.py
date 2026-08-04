"""Verify a blocked origin URL once with an independent HTTP method.

Some public career pages reject an ordinary bounded GET while still exposing a
valid HTTPS endpoint to HEAD. This contract preserves the existing GET as the
primary evidence request. Only a concrete 403 or 405 response may open one HEAD
verification against the resulting URL.

The same HTTP method is never retried. A HEAD error is never accepted. Every
existing redirect, reachability, employer-identity, career-locator, reusable-
origin, locale, and selection gate remains authoritative after verification.
The contract adds no Tavily/LLM call and performs no pipeline or database write.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

import requests

from scripts import run_origin_source_discovery_agent as origin_runtime

_INSTALL_MARKER = "_origin_bounded_head_verification_contract_installed"
_ORIGINAL_HTTP_PROBE = "_origin_bounded_head_verification_original_http_probe"
HEAD_VERIFICATION_ELIGIBLE_STATUSES = frozenset({403, 405})
HEAD_VERIFICATION_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "X-Automation-Client": "job-application-pipeline-origin-source-discovery/0.1",
}


def probe_with_bounded_head_verification(
    original_probe: Callable[..., origin_runtime.OriginDiscoveryProbeResult],
    url: str,
    *,
    timeout_seconds: float,
) -> origin_runtime.OriginDiscoveryProbeResult:
    """Run GET once and, only after 403/405, verify once with HEAD."""

    primary = original_probe(url, timeout_seconds=timeout_seconds)
    if primary.reachable:
        return primary
    if primary.status_code not in HEAD_VERIFICATION_ELIGIBLE_STATUSES:
        return primary

    verification_url = primary.final_url or url
    try:
        response = requests.head(
            verification_url,
            timeout=timeout_seconds,
            headers=dict(HEAD_VERIFICATION_HEADERS),
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        return replace(
            primary,
            reason=(
                f"{primary.reason}; bounded HEAD verification failed: "
                f"{exc.__class__.__name__}"
            ),
        )

    verification = origin_runtime.probe_result_from_http_response(
        verification_url,
        response,
    )
    if not verification.reachable:
        return replace(
            primary,
            reason=(
                f"{primary.reason}; bounded HEAD verification rejected: "
                f"status={verification.status_code}"
            ),
        )

    return replace(
        verification,
        reason=(
            f"{verification.reason}; bounded HEAD verification accepted after "
            f"GET status={primary.status_code}"
        ),
    )


def install_origin_bounded_head_verification_contract() -> None:
    """Install the bounded GET-to-HEAD method transition exactly once."""

    if bool(getattr(origin_runtime, _INSTALL_MARKER, False)):
        return

    original_probe = origin_runtime.http_probe
    setattr(origin_runtime, _ORIGINAL_HTTP_PROBE, original_probe)

    def bounded_probe(
        url: str,
        *,
        timeout_seconds: float,
    ) -> origin_runtime.OriginDiscoveryProbeResult:
        return probe_with_bounded_head_verification(
            original_probe,
            url,
            timeout_seconds=timeout_seconds,
        )

    origin_runtime.http_probe = bounded_probe
    setattr(origin_runtime, _INSTALL_MARKER, True)


__all__ = [
    "HEAD_VERIFICATION_ELIGIBLE_STATUSES",
    "HEAD_VERIFICATION_HEADERS",
    "install_origin_bounded_head_verification_contract",
    "probe_with_bounded_head_verification",
]
