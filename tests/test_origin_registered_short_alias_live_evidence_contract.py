from __future__ import annotations

import scripts.run_origin_url_default_repair as default_entry  # noqa: F401
from src.search_intelligence.origin_registered_short_alias_live_evidence_contract import (
    REGISTERED_EXACT_HOST_IDENTITY_ALIASES,
)
import src.search_intelligence.origin_source_discovery_agent as origin_agent


def _assessment(
    *,
    url: str,
    company_key: str,
    company_name: str,
    title: str = "Karriere",
) -> origin_agent.OriginDiscoveryAssessment:
    candidate = origin_agent.OriginDiscoveryCandidate(
        url=url,
        provider=origin_agent.SEARCH_PROVIDER_KIND,
        reason="live acceptance candidate",
        source_priority=8,
        evidence={
            "title": title,
            "snippet": "Official careers",
            "query": f'"{company_name}" Karriere',
        },
    )
    return origin_agent.assess_origin_candidate(
        candidate,
        company_key=company_key,
        company_name=company_name,
        probe=lambda candidate_url: origin_agent.OriginDiscoveryProbeResult(
            url=candidate_url,
            final_url=candidate_url,
            status_code=200,
            reachable=True,
            career_like=True,
            title=title,
            reason="reachable career/job-like URL",
        ),
    )


def test_cgm_exact_host_identity_survives_generic_live_title() -> None:
    assessment = _assessment(
        url="https://www.cgm.com/corp_de/karriere.html",
        company_key="compugroup_medical",
        company_name="CompuGroup Medical SE & Co. KGaA",
    )

    assert REGISTERED_EXACT_HOST_IDENTITY_ALIASES["compugroup_medical"] == (
        "cgm",
    )
    assert assessment.decision == "select_candidate"
    assert any(
        "audited exact-host identity alias" in reason
        for reason in assessment.reasons
    )


def test_eon_group_host_requires_entity_token_in_origin_path() -> None:
    accepted = _assessment(
        url=(
            "https://www.eon.com/de/ueber-uns/karriere/"
            "unsere-gesellschaften/digital-technology.html"
        ),
        company_key="e_on_digital_technology",
        company_name="E.ON Digital Technology GmbH",
    )
    ambiguous = _assessment(
        url="https://www.eon.com/de/karriere",
        company_key="e_on_digital_technology",
        company_name="E.ON Digital Technology GmbH",
    )

    assert accepted.decision == "select_candidate"
    assert any(
        "distinctive employer entity token found in origin path" in reason
        for reason in accepted.reasons
    )
    assert ambiguous.decision != "select_candidate"


def test_tib_collision_remains_review_only() -> None:
    assessment = _assessment(
        url="https://www.tib.com/de/karriere",
        company_key="technische_informationsbibliothek_tib",
        company_name="Technische Informationsbibliothek TIB",
        title="TIB Chemicals Careers",
    )

    assert assessment.decision != "select_candidate"
