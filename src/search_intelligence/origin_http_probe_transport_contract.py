"""Install one browser-compatible HTTP profile for bounded origin probing.

Some public corporate career pages reject the runtime's project-specific bot-like
User-Agent before the normal origin gates can observe page content. The transport
contract changes only the headers of the existing single read-only GET request.
It does not retry, accept an HTTP error, lower a selection threshold, bypass any
identity or origin-quality gate, call a provider, or mutate pipeline state.
"""

from __future__ import annotations

import requests

from scripts import run_origin_source_discovery_agent as origin_runtime

_INSTALL_MARKER = "_origin_http_probe_transport_contract_installed"
_ORIGINAL_HTTP_PROBE = "_origin_http_probe_transport_original_http_probe"

ORIGIN_HTTP_PROBE_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "X-Automation-Client": "job-application-pipeline-origin-source-discovery/0.1",
}


def install_origin_http_probe_transport_contract() -> None:
    """Replace the raw probe exactly once while preserving all decision gates."""

    if bool(getattr(origin_runtime, _INSTALL_MARKER, False)):
        return

    setattr(origin_runtime, _ORIGINAL_HTTP_PROBE, origin_runtime.http_probe)

    def browser_compatible_http_probe(
        url: str,
        *,
        timeout_seconds: float,
    ) -> origin_runtime.OriginDiscoveryProbeResult:
        try:
            response = requests.get(
                url,
                timeout=timeout_seconds,
                headers=dict(ORIGIN_HTTP_PROBE_HEADERS),
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            return origin_runtime.OriginDiscoveryProbeResult(
                url=url,
                final_url=None,
                status_code=None,
                reachable=False,
                career_like=False,
                reason=f"request failed: {exc.__class__.__name__}",
            )
        return origin_runtime.probe_result_from_http_response(url, response)

    origin_runtime.http_probe = browser_compatible_http_probe
    setattr(origin_runtime, _INSTALL_MARKER, True)


__all__ = [
    "ORIGIN_HTTP_PROBE_HEADERS",
    "install_origin_http_probe_transport_contract",
]
