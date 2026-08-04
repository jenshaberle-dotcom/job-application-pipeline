from __future__ import annotations

import scripts.run_origin_url_default_repair as default_entry  # noqa: F401
import src.search_intelligence.origin_source_discovery as origin_discovery
import src.search_intelligence.origin_source_discovery_agent as origin_agent


def _probe(
    url: str,
    *,
    title: str,
) -> origin_agent.OriginDiscoveryProbeResult:
    return origin_agent.OriginDiscoveryProbeResult(
        url=url,
        final_url=url,
        status_code=200,
        reachable=True,
        career_like=True,
        title=title,
        reason="reachable career/job-like URL",
    )


def _assess(
    *,
    url: str,
    company_key: str,
    company_name: str,
    title: str,
    provider: str = origin_agent.SEARCH_PROVIDER_KIND,
) -> origin_agent.OriginDiscoveryAssessment:
    candidate = origin_agent.OriginDiscoveryCandidate(
        url=url,
        provider=provider,
        reason="test candidate",
        source_priority=8,
        evidence={
            "title": title,
            "snippet": f"Jobs and careers at {company_name}",
            "query": f'"{company_name}" Karriere',
        },
    )
    return origin_agent.assess_origin_candidate(
        candidate,
        company_key=company_key,
        company_name=company_name,
        probe=lambda candidate_url: _probe(candidate_url, title=title),
    )


def test_third_party_path_identity_cannot_become_tib_origin() -> None:
    assessment = _assess(
        url=(
            "https://eujobs.co/career-guides/"
            "technische-informationsbibliothek-tib-german-national-library-"
            "of-science-and-technology-career-guide"
        ),
        company_key="technische_informationsbibliothek_tib",
        company_name="Technische Informationsbibliothek TIB",
        title="Technische Informationsbibliothek TIB Career Guide",
    )

    assert assessment.decision != "select_candidate"
    assert origin_discovery.is_known_aggregator_domain("eujobs.co") is True


def test_unknown_third_party_host_cannot_win_from_path_and_search_context() -> None:
    assessment = _assess(
        url="https://career-guides.example/companies/acme-employer/jobs",
        company_key="acme_employer",
        company_name="Acme Employer GmbH",
        title="Acme Employer Careers",
    )

    assert assessment.decision == "reject"
    assert any("origin host is not employer-bound" in item for item in assessment.reasons)


def test_symbol_brand_employer_host_remains_selectable() -> None:
    assessment = _assess(
        url="https://career.1and1.org/",
        company_key="1_1",
        company_name="1&1",
        title="1&1 Careers",
        provider=origin_agent.GENERATED_PROVIDER_KIND,
    )

    assert assessment.decision == "select_candidate"


def test_tenant_ats_does_not_require_employer_name_in_platform_host() -> None:
    assessment = _assess(
        url="https://careers.smartrecruiters.com/ComputerFutures3",
        company_key="computer_futures",
        company_name="Computer Futures",
        title="Computer Futures Careers",
    )

    assert assessment.decision == "select_candidate"
