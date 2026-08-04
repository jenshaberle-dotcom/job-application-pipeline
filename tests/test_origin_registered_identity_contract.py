from __future__ import annotations

import scripts.run_origin_url_default_repair as default_entry  # noqa: F401
from src.search_intelligence import adaptive_origin_search as adaptive
from src.search_intelligence.origin_registered_identity_contract import (
    REGISTERED_ORIGIN_IDENTITY_ALIASES,
)
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
        reason="reviewed official benchmark candidate",
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


def test_registry_contains_identity_aliases_not_urls() -> None:
    assert REGISTERED_ORIGIN_IDENTITY_ALIASES["compugroup_medical"][0] == "cgm"
    assert REGISTERED_ORIGIN_IDENTITY_ALIASES["bridgingit"][0] == "bridging-it"
    assert REGISTERED_ORIGIN_IDENTITY_ALIASES["e_on_digital_technology"][0] == "eon"
    assert all(
        "://" not in alias
        for aliases in REGISTERED_ORIGIN_IDENTITY_ALIASES.values()
        for alias in aliases
    )


def test_registered_aliases_receive_bounded_search_priority() -> None:
    cgm_surfaces = adaptive.brand_surface_variants(
        company_name="CompuGroup Medical SE & Co. KGaA",
        company_key="compugroup_medical",
    )
    eon_surfaces = adaptive.brand_surface_variants(
        company_name="E.ON Digital Technology GmbH",
        company_key="e_on_digital_technology",
    )
    bridging_surfaces = adaptive.brand_surface_variants(
        company_name="bridgingIT GmbH",
        company_key="bridgingit",
    )

    assert cgm_surfaces[1] == "cgm"
    assert eon_surfaces[1] == "eon"
    assert bridging_surfaces[1] == "bridging-it"

    cgm_queries = adaptive.initial_adaptive_queries(
        company_name="CompuGroup Medical SE & Co. KGaA",
        company_key="compugroup_medical",
        target_location="Hannover",
        maximum=4,
    )
    eon_queries = adaptive.initial_adaptive_queries(
        company_name="E.ON Digital Technology GmbH",
        company_key="e_on_digital_technology",
        target_location="Hannover",
        maximum=4,
    )

    assert cgm_queries[-1] == '"cgm" Karriere'
    assert eon_queries[-1] == '"eon" Karriere'


def test_reviewed_official_origin_shapes_pass_all_current_gates() -> None:
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
            "X1F | Jobs & Stellenangebote",
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


def test_unregistered_or_non_numeric_short_acronyms_remain_review_only() -> None:
    ivv = _assessment(
        url="https://www.ivv.fraunhofer.de/de/jobs-karriere.html",
        company_key="ivv",
        company_name="IVV",
        title="Fraunhofer IVV Jobs und Karriere",
    )
    tib = _assessment(
        url="https://www.tib.com/de/karriere",
        company_key="technische_informationsbibliothek_tib",
        company_name="Technische Informationsbibliothek TIB",
        title="TIB Chemicals Careers",
    )

    assert ivv.decision != "select_candidate"
    assert tib.decision != "select_candidate"
