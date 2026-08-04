from __future__ import annotations

from typing import Any

import requests

import scripts.run_origin_url_default_repair as default_entry  # noqa: F401
import src.search_intelligence.origin_source_discovery_agent as origin_agent


EON_URL = (
    "https://www.eon.com/de/ueber-uns/karriere/"
    "unsere-gesellschaften/digital-technology.html"
)
SITEMAP_URL = "https://www.eon.com/sitemap.xml"


def _candidate(*, provider: str = "operator_supplied_unvalidated") -> origin_agent.OriginDiscoveryCandidate:
    return origin_agent.OriginDiscoveryCandidate(
        url=EON_URL,
        provider=provider,
        reason="operator hint; still requires deterministic validation",
        source_priority=8,
    )


def _challenge_probe(candidate_url: str) -> origin_agent.OriginDiscoveryProbeResult:
    return origin_agent.OriginDiscoveryProbeResult(
        url=candidate_url,
        final_url=candidate_url,
        status_code=403,
        reachable=False,
        career_like=True,
        response_bytes=5_648,
        title="Just a moment...",
        reason="status=403; career_like=True",
    )


def _assessment(
    monkeypatch,
    *,
    sitemap_content: bytes,
    sitemap_status: int = 200,
    sitemap_final_url: str = SITEMAP_URL,
    provider: str = "operator_supplied_unvalidated",
) -> tuple[origin_agent.OriginDiscoveryAssessment, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    class Response:
        status_code = sitemap_status
        url = sitemap_final_url
        content = sitemap_content
        text = sitemap_content.decode("utf-8", errors="replace")

    def fake_get(url: str, **kwargs: Any) -> Response:
        calls.append({"url": url, **kwargs})
        return Response()

    monkeypatch.setattr(requests, "get", fake_get)
    result = origin_agent.assess_origin_candidate(
        _candidate(provider=provider),
        company_key="e_on_digital_technology",
        company_name="E.ON Digital Technology GmbH",
        probe=_challenge_probe,
    )
    return result, calls


def test_exact_same_origin_sitemap_declaration_selects_operator_url(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sitemap = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>"
        + EON_URL.encode("utf-8")
        + b"</loc></url></urlset>"
    )

    assessment, calls = _assessment(monkeypatch, sitemap_content=sitemap)

    assert assessment.decision == "select_candidate"
    assert assessment.final_url == EON_URL
    assert assessment.probe is not None
    assert assessment.probe.status_code == 403
    assert assessment.probe.reachable is False
    assert len(calls) == 1
    assert calls[0]["url"] == SITEMAP_URL
    assert calls[0]["allow_redirects"] is True
    assert any(
        "exact operator URL declared by same-origin publisher sitemap" in reason
        for reason in assessment.reasons
    )


def test_sitemap_without_exact_operator_url_remains_rejected(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sitemap = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<urlset><url><loc>https://www.eon.com/de/karriere</loc></url></urlset>"
    )

    assessment, calls = _assessment(monkeypatch, sitemap_content=sitemap)

    assert assessment.decision == "reject"
    assert len(calls) == 1
    assert any(
        "same-origin sitemap did not declare the exact operator URL" in reason
        for reason in assessment.reasons
    )


def test_sitemap_redirect_to_other_host_cannot_select(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sitemap = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<urlset><url><loc>"
        + EON_URL.encode("utf-8")
        + b"</loc></url></urlset>"
    )

    assessment, calls = _assessment(
        monkeypatch,
        sitemap_content=sitemap,
        sitemap_final_url="https://example.com/sitemap.xml",
    )

    assert assessment.decision == "reject"
    assert len(calls) == 1
    assert any(
        "sitemap redirect left the operator origin" in reason
        for reason in assessment.reasons
    )


def test_generated_candidate_never_opens_sitemap_evidence(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def unexpected_get(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Generated candidates must not use operator sitemap evidence")

    monkeypatch.setattr(requests, "get", unexpected_get)
    assessment = origin_agent.assess_origin_candidate(
        _candidate(provider="generated_company_domain_candidate"),
        company_key="e_on_digital_technology",
        company_name="E.ON Digital Technology GmbH",
        probe=_challenge_probe,
    )

    assert assessment.decision == "reject"


def test_generic_403_without_exact_challenge_title_never_opens_sitemap(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def unexpected_get(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("A generic HTTP 403 must not open sitemap evidence")

    def generic_forbidden(candidate_url: str) -> origin_agent.OriginDiscoveryProbeResult:
        return origin_agent.OriginDiscoveryProbeResult(
            url=candidate_url,
            final_url=candidate_url,
            status_code=403,
            reachable=False,
            career_like=True,
            response_bytes=500,
            title="Forbidden",
            reason="status=403; career_like=True",
        )

    monkeypatch.setattr(requests, "get", unexpected_get)
    assessment = origin_agent.assess_origin_candidate(
        _candidate(),
        company_key="e_on_digital_technology",
        company_name="E.ON Digital Technology GmbH",
        probe=generic_forbidden,
    )

    assert assessment.decision == "reject"
