from __future__ import annotations

from src.search_intelligence.origin_search_runtime_contract import (
    install_origin_search_runtime_contract,
)
from src.search_intelligence.origin_quality_contract import (
    canonical_origin_from_job_detail,
    is_job_detail_url,
)
import src.search_intelligence.origin_source_discovery_agent as origin_agent

install_origin_search_runtime_contract()


def _probe(url: str, *, title: str = "Employer Careers") -> origin_agent.OriginDiscoveryProbeResult:
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
    provider: str = origin_agent.SEARCH_PROVIDER_KIND,
    title: str = "Employer Careers",
    snippet: str = "Jobs and careers",
    probe_title: str | None = None,
) -> origin_agent.OriginDiscoveryAssessment:
    candidate = origin_agent.OriginDiscoveryCandidate(
        url=url,
        provider=provider,
        reason="test candidate",
        source_priority=8,
        evidence={"title": title, "snippet": snippet, "query": company_name},
    )
    return origin_agent.assess_origin_candidate(
        candidate,
        company_key=company_key,
        company_name=company_name,
        probe=lambda candidate_url: _probe(
            candidate_url,
            title=probe_title or title,
        ),
    )


def test_malformed_long_dns_label_fails_closed_before_probe() -> None:
    overlong = "a" * 64
    assert origin_agent.normalize_candidate_url(f"https://{overlong}.de/jobs") is None


def test_generic_homepage_cannot_auto_select_from_body_career_signal() -> None:
    assessment = _assess(
        url="https://commercetools.com/",
        company_key="commercetools",
        company_name="commercetools GmbH",
        title="commercetools Careers",
    )

    assert assessment.decision == "manual_review_candidate"
    assert "generic company page lacks a career/job origin locator" in assessment.reasons


def test_third_party_company_profile_cannot_become_origin() -> None:
    assessment = _assess(
        url="https://www.levels.fyi/companies/computer-futures",
        company_key="computer_futures",
        company_name="Computer Futures",
        title="Computer Futures Careers and Jobs",
        snippet="Computer Futures company profile, salaries and careers",
    )

    assert assessment.decision != "select_candidate"


def test_job_detail_is_not_selected_as_reusable_origin() -> None:
    assessment = _assess(
        url="https://jobs.clarios.com/posting/energy-portfolio-lead-m-f-d/WD46504/",
        company_key="clarios_germany",
        company_name="Clarios Germany GmbH & Co. KG",
        title="Energy Portfolio Lead | Clarios Careers",
    )

    assert assessment.decision == "manual_review_candidate"
    assert "job-detail evidence is not a reusable origin source" in assessment.reasons


def test_job_detail_generates_conservative_portal_hypotheses() -> None:
    assert canonical_origin_from_job_detail(
        "https://jobs.computacenter.com/job/Hatfield-GIS-BISO/1402282333"
    ) == "https://jobs.computacenter.com/"
    assert canonical_origin_from_job_detail(
        "https://job-boards.greenhouse.io/zscaler/jobs/5193808007"
    ) == "https://job-boards.greenhouse.io/zscaler"
    assert is_job_detail_url("https://job-boards.greenhouse.io/zscaler") is False


def test_search_conversion_places_portal_before_job_detail() -> None:
    candidates = origin_agent.search_results_to_origin_candidates(
        [
            origin_agent.OriginSearchResult(
                url="https://job-boards.greenhouse.io/zscaler/jobs/5193808007",
                title="Zscaler job",
                snippet="Zscaler careers",
                query="Zscaler careers",
                provider="tavily",
            )
        ]
    )

    assert candidates[0].url == "https://job-boards.greenhouse.io/zscaler"
    assert candidates[1].url == "https://job-boards.greenhouse.io/zscaler/jobs/5193808007"


def test_short_acronym_collision_requires_review() -> None:
    tib = _assess(
        url="https://www.tib.com/de/karriere",
        company_key="technische_informationsbibliothek_tib",
        company_name="Technische Informationsbibliothek (TIB)",
        provider=origin_agent.GENERATED_PROVIDER_KIND,
        title="TIB Chemicals Careers",
        probe_title="TIB Chemicals Careers",
    )
    ivv = _assess(
        url="https://www.ivv.fraunhofer.de/de/jobs-karriere.html",
        company_key="ivv",
        company_name="IVV",
        title="Fraunhofer IVV Jobs und Karriere",
    )

    assert tib.decision == "manual_review_candidate"
    assert ivv.decision == "manual_review_candidate"


def test_valid_compound_and_tenant_portals_remain_selectable() -> None:
    adesso = _assess(
        url="https://www.adesso.de/de/jobs-karriere/einstiegsmoeglichkeiten/index.jsp",
        company_key="adesso",
        company_name="adesso SE",
        provider=origin_agent.GENERATED_PROVIDER_KIND,
        title="Jobs und Karriere bei adesso",
    )
    madsack = _assess(
        url="https://www.madsack-karriere.de/",
        company_key="madsack",
        company_name="MADSACK Mediengruppe",
        provider=origin_agent.GENERATED_PROVIDER_KIND,
        title="MADSACK Karriere",
    )
    finanz = _assess(
        url="https://finanz-informatik.onapply.de/",
        company_key="finanz_informatik",
        company_name="Finanz Informatik GmbH & Co. KG",
        title="Karriere bei der Finanz Informatik",
    )

    assert adesso.decision == "select_candidate"
    assert madsack.decision == "select_candidate"
    assert finanz.decision == "select_candidate"


def test_symbol_numeric_career_host_remains_selectable() -> None:
    assessment = _assess(
        url="https://career.1and1.org/",
        company_key="1_1",
        company_name="1&1",
        provider=origin_agent.GENERATED_PROVIDER_KIND,
        title="1&1 Careers",
    )

    assert assessment.decision == "select_candidate"
