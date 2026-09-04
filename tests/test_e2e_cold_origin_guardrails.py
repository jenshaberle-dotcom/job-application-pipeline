from __future__ import annotations

from dataclasses import dataclass

from src.search_intelligence.origin_source_discovery_agent import (
    OriginDiscoveryCandidate,
    OriginDiscoveryProbeResult,
    company_identity_score,
    discover_origin_source,
    probe_result_from_http_response,
)


@dataclass
class FakeResponse:
    status_code: int
    url: str
    text: str
    content: bytes


def test_generated_career_path_does_not_self_validate() -> None:
    response = FakeResponse(
        status_code=200,
        url="https://example.test/karriere",
        text="<html><title>Example Domain</title><body>Welcome</body></html>",
        content=b"example",
    )

    probe = probe_result_from_http_response(
        "https://example.test/karriere",
        response,
    )

    assert probe.reachable is True
    assert probe.career_like is False


def test_server_redirect_can_supply_independent_career_evidence() -> None:
    response = FakeResponse(
        status_code=200,
        url="https://jobs.example.test/openings",
        text="<html><title>Example</title></html>",
        content=b"example",
    )

    probe = probe_result_from_http_response(
        "https://example.test/",
        response,
    )

    assert probe.reachable is True
    assert probe.career_like is True


def test_live_company_homepage_without_career_evidence_cannot_auto_select() -> None:
    def probe(url: str) -> OriginDiscoveryProbeResult:
        return OriginDiscoveryProbeResult(
            url=url,
            final_url=url,
            status_code=200,
            reachable=True,
            career_like=False,
            title="Company homepage",
            reason="status=200; career_like=False",
        )

    result = discover_origin_source(
        company_key="adnova_software_und_services",
        company_name="ADNOVA Software und Services GmbH",
        search_result_candidates=(
            OriginDiscoveryCandidate(
                url="https://adnova.com/",
                provider="test",
                reason="cold cohort regression",
                source_priority=1,
            ),
        ),
        probe=probe,
        max_generated_candidates=0,
    )

    assert result.decision == "manual_review_required"
    assert result.selected_url is None


def test_all_caps_brand_is_not_double_counted_as_identity_and_acronym() -> None:
    score, reasons = company_identity_score(
        url="https://simcon.com/",
        company_key="simcon",
        company_name="SIMCON",
    )

    assert score == 0.55
    assert score < 0.78
    assert "company token found in host" in reasons


def test_not_found_confidence_ignores_unreachable_hypothesis() -> None:
    def probe(url: str) -> OriginDiscoveryProbeResult:
        return OriginDiscoveryProbeResult(
            url=url,
            final_url=None,
            status_code=None,
            reachable=False,
            career_like=False,
            reason="request failed: ConnectionError",
        )

    result = discover_origin_source(
        company_key="pluyion",
        company_name="Pluyion GmbH",
        search_result_candidates=(
            OriginDiscoveryCandidate(
                url="https://jobs.pluyion.com/",
                provider="test",
                reason="cold cohort regression",
                source_priority=1,
            ),
        ),
        probe=probe,
        max_generated_candidates=0,
    )

    assert result.decision == "not_found"
    assert result.selected_url is None
    assert result.confidence_score == 0.0
