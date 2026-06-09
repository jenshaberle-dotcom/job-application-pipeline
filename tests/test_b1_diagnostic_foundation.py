from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.search_intelligence.b1_diagnostic_foundation import (
    SAFETY_BOUNDARY,
    Sensor001FSampleResult,
    build_b1_diagnostic_foundation_report,
    build_sensor001f_decision_scaffold,
)
from src.search_intelligence.market_sensor_coverage import MarketSensorProfile
from src.search_intelligence.stepstone_company_discovery_cycle import CompanyCooldown, CompanyObservation


def test_b1_safety_boundary_is_read_only() -> None:
    assert SAFETY_BOUNDARY["read_only_diagnostic"] is True
    for key, value in SAFETY_BOUNDARY.items():
        if key != "read_only_diagnostic":
            assert value is False


def test_b1_report_exposes_market_gap_stepstone_cycle_and_sensor_decision_scaffold() -> None:
    now = datetime(2026, 6, 8, 19, 0, tzinfo=UTC)
    report = build_b1_diagnostic_foundation_report(
        market_profiles=(
            MarketSensorProfile(
                profile_key="ba_local_hannover",
                source_name="bundesagentur",
                search_location="Hannover",
                search_terms=("Data Engineer",),
                is_active=True,
            ),
        ),
        stepstone_cooldowns=(
            CompanyCooldown(
                company_key="hdi",
                company_name="HDI Gruppe",
                source_name="stepstone",
                search_profile_name="data_engineering_hannover",
                search_term="Data Engineer",
                cooldown_until=now + timedelta(days=3),
                reason="known repeated company block",
                evidence_count=5,
            ),
        ),
        stepstone_observations=(
            CompanyObservation(
                company_key="bahlsen",
                company_name="Bahlsen",
                title="Data Engineer Analytics Platform",
            ),
        ),
        now=now,
    ).as_dict()

    assert report["schema_version"] == "b1.market_stepstone_sensor_diagnostic_foundation.v1"
    market_assessment = report["market_001"]["assessments"][0]
    assert market_assessment["status"] == "gap_detected"
    assert "missing_germany_wide_remote_options_profile" in market_assessment["coverage_gaps"]
    assert report["stepstone_001"]["discovery_plan"]["action"] == "run_fetch_time_company_not_probe"
    assert report["stepstone_001"]["discovery_assessment"]["new_company_count"] == 1
    assert report["sensor_001f"]["status"] == "awaiting_sensor001e_sample_result"
    assert report["sensor_001f"]["recommended_decision"] == "do_not_decide_before_bounded_sample_result"


def test_sensor001f_scaffold_blocks_decision_without_sample_result() -> None:
    scaffold = build_sensor001f_decision_scaffold().as_dict()

    assert scaffold["status"] == "awaiting_sensor001e_sample_result"
    assert scaffold["missing_metrics"]
    assert scaffold["recommended_decision"] == "do_not_decide_before_bounded_sample_result"


def test_sensor001f_can_recommend_controlled_activation_for_good_complete_sample() -> None:
    scaffold = build_sensor001f_decision_scaffold(
        Sensor001FSampleResult(
            total_loaded=20,
            inserted_count=10,
            duplicate_count=10,
            distinct_company_count=8,
            new_company_count=4,
            remote_signal_count=12,
            profile_relevant_title_count=14,
            irrelevant_title_count=3,
            error_count=0,
        )
    ).as_dict()

    assert scaffold["status"] == "decision_ready"
    assert scaffold["missing_metrics"] == []
    assert scaffold["recommended_decision"] == "activate_controlled_profile"
