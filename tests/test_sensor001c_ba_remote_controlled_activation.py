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
    build_ba_remote_controlled_activation_review,
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
        id=2,
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


def test_controlled_activation_review_reports_migration_pending_before_profile_exists() -> None:
    review = build_ba_remote_controlled_activation_review((local_profile(),), ())

    payload = review.as_dict()

    assert payload["overall_status"] == "migration_pending"
    assert "migration is pending" in " ".join(payload["findings"])
    assert payload["safety_boundary"]["productive_activation"] is False


def test_controlled_activation_review_reports_ready_for_inactive_profile() -> None:
    review = build_ba_remote_controlled_activation_review(
        (local_profile(), review_profile()),
        review_terms(),
    )

    payload = review.as_dict()

    assert payload["overall_status"] == "review_profile_ready"
    assert "Inactive BA remote/nationwide review profile exists" in " ".join(payload["findings"])
    assert payload["safety_boundary"]["scheduler_mutation"] is False


def test_controlled_activation_review_stops_if_profile_is_active() -> None:
    review = build_ba_remote_controlled_activation_review(
        (local_profile(), review_profile(is_active=True)),
        review_terms(),
    )

    payload = review.as_dict()

    assert payload["overall_status"] == "unsafe_active_profile_detected"
    assert "not allowed" in " ".join(payload["findings"])


def test_migration_creates_inactive_review_profile_only() -> None:
    migration = Path("db/migrations/074_create_ba_remote_nationwide_review_profile.sql").read_text(encoding="utf-8")

    assert "ba_data_engineering_remote_nationwide_review" in migration
    assert "FALSE" in migration
    assert "ROLLBACK" not in migration
    assert "DELETE FROM" not in migration.upper()
    assert "UPDATE search_profiles" not in migration


def test_sensor001c_script_is_directly_executable_from_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_sensor001c_ba_remote_controlled_activation_review.py",
            "--help",
        ],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Review SENSOR-001C" in result.stdout
