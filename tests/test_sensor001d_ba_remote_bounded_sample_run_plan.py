from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from src.search_intelligence.market_sensor_controlled_activation import (
    BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
    BA_SOURCE_NAME,
    EXPECTED_BA_REMOTE_TERMS,
    MarketSensorProfileState,
    MarketSensorTermState,
)
from src.search_intelligence.market_sensor_sample_run_plan import (
    build_ba_remote_bounded_sample_run_plan,
)


def local_profile() -> MarketSensorProfileState:
    return MarketSensorProfileState(
        id=1,
        profile_name="ba_data_engineer_30629_50km",
        source_name=BA_SOURCE_NAME,
        search_term="Data Engineer",
        search_location="30629",
        search_radius_km=50,
        offer_type=1,
        page_size=10,
        is_active=True,
    )


def review_profile(*, is_active: bool = False) -> MarketSensorProfileState:
    return MarketSensorProfileState(
        id=20,
        profile_name=BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
        source_name=BA_SOURCE_NAME,
        search_term="Data Engineer",
        search_location=None,
        search_radius_km=None,
        offer_type=1,
        page_size=10,
        is_active=is_active,
    )


def review_terms() -> tuple[MarketSensorTermState, ...]:
    return tuple(
        MarketSensorTermState(
            profile_name=BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
            search_term=term,
            is_active=True,
        )
        for term in EXPECTED_BA_REMOTE_TERMS
    )


def test_bounded_sample_run_plan_is_ready_when_review_profile_ready() -> None:
    plan = build_ba_remote_bounded_sample_run_plan(
        (local_profile(), review_profile()),
        review_terms(),
        max_terms=2,
    )

    payload = plan.as_dict()

    assert payload["overall_status"] == "sample_plan_ready"
    assert payload["review_status"] == "review_profile_ready"
    assert payload["sample_terms"] == ["Data Engineer", "Analytics Engineer"]
    assert payload["sample_limits"]["max_terms"] == 2
    assert payload["sample_limits"]["page_size_per_term"] == 10
    assert payload["sample_limits"]["max_raw_results_seen"] == 20
    assert payload["activation_changes"]["run_sample_now"] is False
    assert payload["activation_changes"]["activate_profile_now"] is False
    assert payload["safety_boundary"]["ingestion_run"] is False


def test_bounded_sample_run_plan_blocks_before_review_profile_exists() -> None:
    plan = build_ba_remote_bounded_sample_run_plan((local_profile(),), (), max_terms=2)

    payload = plan.as_dict()

    assert payload["overall_status"] == "blocked_until_review_profile_ready"
    assert payload["review_status"] == "migration_pending"
    assert payload["sample_terms"] == []
    assert payload["activation_changes"]["run_sample_now"] is False


def test_bounded_sample_run_plan_blocks_if_review_profile_is_active() -> None:
    plan = build_ba_remote_bounded_sample_run_plan(
        (local_profile(), review_profile(is_active=True)),
        review_terms(),
        max_terms=2,
    )

    payload = plan.as_dict()

    assert payload["overall_status"] == "blocked_until_review_profile_ready"
    assert payload["review_status"] == "unsafe_active_profile_detected"
    assert payload["sample_terms"] == []
    assert payload["activation_changes"]["run_sample_now"] is False


def test_bounded_sample_run_plan_respects_max_terms() -> None:
    plan = build_ba_remote_bounded_sample_run_plan(
        (local_profile(), review_profile()),
        review_terms(),
        max_terms=1,
    )

    payload = plan.as_dict()

    assert payload["sample_terms"] == ["Data Engineer"]
    assert payload["sample_limits"]["max_raw_results_seen"] == 10


def test_sensor001d_script_is_directly_executable_from_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_sensor001d_ba_remote_bounded_sample_run_plan.py",
            "--help",
        ],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Generate SENSOR-001D" in result.stdout
