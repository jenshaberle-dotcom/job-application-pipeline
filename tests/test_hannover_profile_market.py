"""Profile-market expansion is separate from registry coverage and job qualification."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.connectors.hannover_tech_registry_poc import analyze, population
from src.search_intelligence.hannover_profile_market import (
    PROFILE_SCHEMA, expand_hannover_market, title_role_families,
)

FIXTURE = Path("examples/hannover-tech-registry-poc")


def load(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def seed(company_name, sector="FINANCE_INSURANCE",
         website="https://insurance.example", source="regional-directory"):
    return {
        "company_name": company_name,
        "geography": "REGION_HANNOVER",
        "sector": sector,
        "website": website,
        "source_name": source,
        "source_url": "https://example.com/region/hannover",
    }


@pytest.mark.parametrize("title", [
    "Lösungsarchitekt Digitale Innovationen (m/w/d)",
    "Solution Architect – Banking Platforms",
    "Senior Solutions Architect",
    "IT-Lösungsarchitekt Cloud",
    "AI Solution Architect",
    "Cloud Solution Architect",
    "Integration Architect",
    "IT-Architekt (m/w/d) Anwendungsentwicklung Komposit",
    "Anwendungsarchitekt",
    "Softwarearchitekt",
    "Enterprise Architect",
    "Technical Architect",
])
def test_solution_architecture_matches_explicit_role_titles(title):
    assert "solution_architecture" in title_role_families(title)


@pytest.mark.parametrize("title", [
    "Architekt Hochbau",
    "Solution Consultant – Sales",
    "System Engineer",
    "Kundenberater Versicherung",
    "Cloud Data Engineer",
    "Softwareentwickler Java",
])
def test_solution_architecture_does_not_match_unrelated_titles(title):
    assert "solution_architecture" not in title_role_families(title)


def test_solution_architecture_is_additional_to_previous_role_families():
    assert "data_engineering" in title_role_families("Cloud Data Engineer")
    assert "product_ownership" in title_role_families("Technical Product Owner")
    assert "systems_engineering" in title_role_families("Systems Engineer")
    assert "ai_engineering" in title_role_families("AI Engineer")


def test_extended_market_keeps_original_census_immutable_and_separate():
    baseline = population(load("census.json"))
    before = deepcopy(baseline)
    extension = {"schema_version": PROFILE_SCHEMA, "companies": [
        seed("Alpha Analytics GmbH", "CONSULTING", "https://alpha.example"),
        seed("Regional Insurance Group"),
    ]}
    expanded, audit = expand_hannover_market(baseline, extension)
    assert baseline == before
    assert audit["tech_baseline"] == 3
    assert audit["new_profile_market_candidates"] == 1
    assert audit["overlapping_source_records"] == 1
    assert audit["expanded_total"] == 4
    assert len(expanded) == 4
    alpha = next(x for x in expanded if x["company_key"] == "alpha")
    assert alpha["poc_population_segment"] == "TECH_BASELINE"
    assert alpha["websites"] == ["https://alpha.example"]
    assert alpha["poc_source_records"][0]["authority"] == "UNVERIFIED_DIRECTORY_SEED"
    insurance = next(x for x in expanded
                     if x["company_name"] == "Regional Insurance Group")
    assert insurance["scope_memberships"] == [
        {"geography": "REGION_HANNOVER", "cohort": "PROFILE_MARKET"}
    ]
    assert insurance["poc_role_fit_status"] == "NOT_ASSESSED_UNTIL_JOB_EVIDENCE"


def test_real_census_role_expansion_reports_two_denominators():
    census = load("census.json")
    catalog = json.loads(
        Path("contracts/connector-capability-catalog-v1.json").read_text(encoding="utf-8")
    )
    expansion = {"schema_version": PROFILE_SCHEMA,
                 "companies": [seed("Regional Insurance Group")]}
    result = analyze(
        census, load("openjobs.json"), load("boards.json"), catalog,
        expanded_companies=expansion,
    )
    assert result["total"] == 4
    assert result["scope"] == "REGION_HANNOVER:PROFILE_MARKET"
    assert result["population_audit"]["tech_baseline"] == 3
    assert result["population_audit"]["new_profile_market_candidates"] == 1
    assert result["by_segment"]["TECH_BASELINE"]["population"] == 3
    assert result["by_segment"]["PROFILE_MARKET_ADDITION"]["population"] == 1
    assert result["summary"]["registry_company_match"] == 2
    assert result["summary"]["long_tail_registry_gap"] == 2
    assert result["summary"]["verified_portal"] == 0
    assert result["summary"]["long_tail_portal_gap"] is None
    assert result["summary"]["target_role_jobs_observed"] == 0


def test_same_domain_does_not_merge_unrelated_employers():
    baseline = population(load("census.json"))
    companies = [
        seed("Regional Insurance Group", website="https://group.example"),
        seed("Regional Insurance IT GmbH", "PUBLIC_IT", "https://group.example"),
    ]
    expanded, audit = expand_hannover_market(
        baseline, {"schema_version": PROFILE_SCHEMA, "companies": companies}
    )
    assert audit["new_profile_market_candidates"] == 2
    assert len({row["company_key"] for row in expanded}) == 5


def test_rejects_offregion_or_unknown_source_provenance():
    baseline = population(load("census.json"))
    invalid = seed("Example outside region")
    invalid["geography"] = "WOLFSBURG"
    with pytest.raises(ValueError, match="identity_geography_or_lineage"):
        expand_hannover_market(
            baseline, {"schema_version": PROFILE_SCHEMA, "companies": [invalid]}
        )
    invalid["geography"] = "REGION_HANNOVER"
    invalid["source_url"] = "http://unsafe.invalid"
    with pytest.raises(ValueError, match="identity_geography_or_lineage"):
        expand_hannover_market(
            baseline, {"schema_version": PROFILE_SCHEMA, "companies": [invalid]}
        )
