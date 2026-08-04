from __future__ import annotations

import scripts.run_origin_url_default_repair as default_entry  # noqa: F401
from src.search_intelligence import adaptive_origin_search as adaptive
import src.search_intelligence.origin_source_discovery_agent as origin_agent


def _assessment(
    *,
    url: str,
    company_key: str,
    company_name: str,
    title: str,
) -> origin_agent.OriginDiscoveryAssessment:
    candidate = origin_agent.OriginDiscoveryCandidate(
        url=url,
        provider=origin_agent.SEARCH_PROVIDER_KIND,
        reason="official benchmark candidate",
        source_priority=8,
        evidence={
            "title": title,
            "snippet": f"Official jobs and careers at {company_name}",
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


def test_high_value_aliases_precede_compact_legal_name_variants() -> None:
    eon = adaptive.brand_surface_variants(
        company_name="E.ON Digital Technology GmbH",
        company_key="e_on_digital_technology",
    )
    cgm = adaptive.brand_surface_variants(
        company_name="CompuGroup Medical SE & Co. KGaA",
        company_key="compugroup_medical",
    )
    bridging = adaptive.brand_surface_variants(
        company_name="bridgingIT GmbH",
        company_key="bridgingit",
    )

    assert eon[1] == "eon"
    assert "cgm" in cgm[:4]
    assert "bridging-it" in bridging[:4]


def test_initial_queries_spend_fourth_basic_request_on_market_alias() -> None:
    eon_queries = adaptive.initial_adaptive_queries(
        company_name="E.ON Digital Technology GmbH",
        company_key="e_on_digital_technology",
        target_location="Hannover",
        maximum=4,
    )
    cgm_queries = adaptive.initial_adaptive_queries(
        company_name="CompuGroup Medical SE & Co. KGaA",
        company_key="compugroup_medical",
        target_location="Hannover",
        maximum=4,
    )

    assert eon_queries[-1] == '"eon" Karriere'
    assert cgm_queries[-1] == '"cgm" Karriere'


def test_official_benchmark_origin_shapes_pass_current_identity_contract() -> None:
    cases = (
        (
            "https://www.bridging-it.de/karriere/stellenanzeigen/",
            "bridgingit",
            "bridgingIT GmbH",
            "Karriere | bridgingIT",
        ),
        (
            "https://www.cgm.com/corp_de/karriere.html",
            "compugroup_medical",
            "CompuGroup Medical SE & Co. KGaA",
            "Karriere | CompuGroup Medical",
        ),
        (
            "https://jobportal.ratbacherkarriere.de/",
            "ratbacher",
            "Ratbacher GmbH",
            "Ratbacher GmbH | Offene Stellen",
        ),
        (
            "https://www.x1f.one/en/jobs/",
            "x1f",
            "X1F GmbH",
            "x1F | Jobs & Stellenangebote",
        ),
    )

    for url, company_key, company_name, title in cases:
        assessment = _assessment(
            url=url,
            company_key=company_key,
            company_name=company_name,
            title=title,
        )
        assert assessment.decision == "select_candidate", (
            url,
            assessment.decision,
            assessment.reasons,
        )
