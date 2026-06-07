from datetime import UTC, datetime, timedelta

import pytest

from src.search_intelligence.stepstone_company_discovery_cycle import (
    CompanyCooldown,
    CompanyObservation,
    company_not_alias,
    adapt_interval_days,
    assess_discovery_observations,
    build_company_discovery_plan,
    build_cooldown_proposals,
    build_not_query,
    is_not_exclusion_supported_for_term,
)


NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


def cooldown(company_key: str, company_name: str, search_term: str = "Data Engineer", *, days: int = 3, evidence: int = 1) -> CompanyCooldown:
    return CompanyCooldown(
        source_name="stepstone",
        search_profile_name="stepstone_data_engineer_hannover",
        search_term=search_term,
        company_key=company_key,
        company_name=company_name,
        cooldown_until=NOW + timedelta(days=days),
        reason="temporary company cooldown",
        evidence_count=evidence,
    )


def test_not_query_negates_companies_only_and_quotes_them() -> None:
    assert build_not_query("Data Engineer", ["HDI", "Ratiodata SE"]) == 'Data Engineer NOT "HDI" NOT "Ratiodata SE"'

    with pytest.raises(ValueError, match="Company names must not include NOT"):
        build_not_query("Data Engineer", ['NOT "ETL"'])


def test_company_not_alias_prefers_short_stepstone_stable_terms() -> None:
    assert company_not_alias("hdi", "HDI Group") == "HDI"
    assert company_not_alias("finanz_informatik", "Finanz Informatik GmbH & Co. KG") == "Finanz Informatik"
    assert company_not_alias("clarios_germany", "Clarios Germany GmbH & Co. KG") == "Clarios Germany"


def test_not_exclusion_is_whitelisted_per_search_term() -> None:
    assert is_not_exclusion_supported_for_term("Data Engineer") is True
    assert is_not_exclusion_supported_for_term("Analytics Engineer") is True
    assert is_not_exclusion_supported_for_term("ETL") is False


def test_plan_uses_only_active_temporary_company_cooldowns() -> None:
    plan = build_company_discovery_plan(
        source_name="stepstone",
        search_profile_name="stepstone_data_engineer_hannover",
        search_term="Data Engineer",
        cooldowns=[
            cooldown("hdi", "HDI AG", evidence=5),
            cooldown("ratiodata", "Ratiodata SE", days=-1, evidence=9),
            cooldown("adesso", "adesso SE", evidence=3),
        ],
        now=NOW,
    )

    assert plan.action == "run_fetch_time_company_not_probe"
    assert plan.not_company_names == ("HDI", "adesso")
    assert plan.not_company_keys == ("hdi", "adesso")
    assert plan.planned_query == 'Data Engineer NOT "HDI" NOT "adesso"'
    assert plan.boundary["company_cooldowns_are_temporary"] is True
    assert plan.boundary["search_terms_are_not_negated"] is True
    assert plan.boundary["logical_cooldown_pool_is_not_capped"] is True


def test_plan_request_budget_does_not_cap_logical_cooldown_pool() -> None:
    cooldowns = [
        cooldown("hdi", "HDI AG", evidence=10),
        cooldown("ratiodata", "Ratiodata SE", evidence=9),
        cooldown("adesso", "adesso SE", evidence=8),
        cooldown("finanz_informatik", "Finanz Informatik GmbH & Co. KG", evidence=7),
    ]

    wave_0 = build_company_discovery_plan(
        source_name="stepstone",
        search_profile_name="stepstone_data_engineer_hannover",
        search_term="Data Engineer",
        cooldowns=cooldowns,
        max_not_terms_per_request=2,
        exclusion_wave_index=0,
        now=NOW,
    )
    wave_1 = build_company_discovery_plan(
        source_name="stepstone",
        search_profile_name="stepstone_data_engineer_hannover",
        search_term="Data Engineer",
        cooldowns=cooldowns,
        max_not_terms_per_request=2,
        exclusion_wave_index=1,
        now=NOW,
    )

    assert wave_0.not_company_names == ("HDI", "Ratiodata")
    assert wave_1.not_company_names == ("adesso", "Finanz Informatik")
    assert wave_0.boundary["max_not_terms_per_request"] == 2
    assert wave_1.boundary["exclusion_wave_index"] == 1



def test_empty_request_wave_is_explicit_skip_not_duplicate_baseline() -> None:
    plan = build_company_discovery_plan(
        source_name="stepstone",
        search_profile_name="stepstone_data_engineer_hannover",
        search_term="Data Engineer",
        cooldowns=[cooldown("hdi", "HDI AG", evidence=10)],
        max_not_terms_per_request=1,
        exclusion_wave_index=1,
        now=NOW,
    )

    assert plan.action == "skip_empty_exclusion_wave"
    assert plan.planned_query == "Data Engineer"
    assert plan.boundary["cooldown_pool_size"] == 1
    assert plan.boundary["selected_wave_size"] == 0


def test_boundary_exposes_wave_pool_sizes() -> None:
    plan = build_company_discovery_plan(
        source_name="stepstone",
        search_profile_name="stepstone_data_engineer_hannover",
        search_term="Data Engineer",
        cooldowns=[
            cooldown("hdi", "HDI AG", evidence=10),
            cooldown("ratiodata", "Ratiodata SE", evidence=9),
            cooldown("adesso", "adesso SE", evidence=8),
        ],
        max_not_terms_per_request=2,
        exclusion_wave_index=1,
        now=NOW,
    )

    assert plan.not_company_names == ("adesso",)
    assert plan.boundary["cooldown_pool_size"] == 3
    assert plan.boundary["selected_wave_size"] == 1
    assert plan.boundary["wave_start_index"] == 2
    assert plan.boundary["wave_end_index"] == 3

def test_non_whitelisted_search_term_keeps_baseline_query() -> None:
    plan = build_company_discovery_plan(
        source_name="stepstone",
        search_profile_name="stepstone_data_engineer_hannover",
        search_term="ETL",
        cooldowns=[cooldown("hdi", "HDI AG", search_term="ETL")],
        now=NOW,
    )

    assert plan.action == "run_baseline_only"
    assert plan.planned_query == "ETL"
    assert plan.not_company_names == ()


def test_cooldown_proposals_are_created_for_dominant_company_blocks_only() -> None:
    proposals = build_cooldown_proposals(
        [
            CompanyObservation("hdi", "HDI AG", "Platform Engineer Azure"),
            CompanyObservation("hdi", "HDI AG", "Power BI Platform Engineer"),
            CompanyObservation("adesso", "adesso SE", "Senior Data Consultant"),
        ],
        dominant_company_threshold=2,
    )

    assert len(proposals) == 1
    assert proposals[0].company_key == "hdi"
    assert proposals[0].evidence_count == 2
    assert proposals[0].cooldown_days > 0


def test_adaptive_interval_shortens_good_spaces_and_extends_weak_spaces() -> None:
    assert adapt_interval_days(current_interval_days=3, quality_score=0.8) == 2
    assert adapt_interval_days(current_interval_days=1, quality_score=0.9) == 1
    assert adapt_interval_days(current_interval_days=3, quality_score=0.4) == 4
    assert adapt_interval_days(current_interval_days=13, quality_score=0.1, max_interval_days=14) == 14


def test_assessment_keeps_company_learning_separate_from_search_term_negation() -> None:
    assessment = assess_discovery_observations(
        search_term="Data Engineer",
        observations=[
            CompanyObservation("hdi", "HDI AG", "Platform Engineer Azure"),
            CompanyObservation("hdi", "HDI AG", "Power BI Platform Engineer"),
            CompanyObservation("hannover_ruck", "Hannover Rück SE", "IT Cloud Engineer AWS"),
            CompanyObservation("aldi", "ALDI Nord", "Verkäufer in Teilzeit"),
        ],
        cooldown_company_keys=["hdi"],
        current_interval_days=3,
    )

    assert assessment.search_term == "Data Engineer"
    assert assessment.known_cooldown_hit_count == 2
    assert assessment.new_company_count == 2
    assert assessment.relevance_hits == 3
    assert assessment.drift_hits == 1
    assert assessment.cooldown_proposals[0].company_key == "hdi"
