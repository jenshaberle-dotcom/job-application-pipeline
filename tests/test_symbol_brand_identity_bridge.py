from __future__ import annotations

from src.search_intelligence.symbol_brand_identity_bridge import (
    install_symbol_brand_identity_bridge,
    symbol_brand_identity_tokens,
)
import src.search_intelligence.origin_source_discovery_agent as origin_agent


def _career_probe(url: str) -> origin_agent.OriginDiscoveryProbeResult:
    return origin_agent.OriginDiscoveryProbeResult(
        url=url,
        final_url=url,
        status_code=200,
        reachable=True,
        career_like=True,
        response_bytes=1000,
        title="Top Jobs bei 1&1 im IT Bereich finden",
        reason="reachable career/job-like URL",
    )


def test_symbol_brand_tokens_preserve_digits_and_verbalize_symbol() -> None:
    assert symbol_brand_identity_tokens(
        company_name="1&1",
        company_key="1_1",
    ) == ("1and1",)


def test_generated_symbol_brand_host_can_pass_existing_identity_gate() -> None:
    install_symbol_brand_identity_bridge()
    candidate = origin_agent.OriginDiscoveryCandidate(
        url="https://career.1and1.org/",
        provider="deterministic_symbol_brand",
        reason="symbol-aware high-value career host hypothesis",
        source_priority=5,
    )

    assessment = origin_agent.assess_origin_candidate(
        candidate,
        company_key="1_1",
        company_name="1&1",
        probe=_career_probe,
    )

    assert assessment.decision == "select_candidate"
    assert assessment.identity_score >= 0.55
    assert assessment.total_score >= origin_agent.AUTO_SELECT_MIN_SCORE
    assert "company token found in host" in assessment.reasons


def test_pure_numeric_domain_remains_insufficient_identity() -> None:
    install_symbol_brand_identity_bridge()
    candidate = origin_agent.OriginDiscoveryCandidate(
        url="https://career.11.org/",
        provider="deterministic_symbol_brand",
        reason="numeric-only host must not become identity truth",
        source_priority=5,
    )

    assessment = origin_agent.assess_origin_candidate(
        candidate,
        company_key="1_1",
        company_name="1&1",
        probe=_career_probe,
    )

    assert assessment.decision == "reject"
    assert assessment.identity_score < 0.45
