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
from src.search_intelligence.sensor001g_ba_remote_controlled_activation_gate import (
    CONFIRMATION_TOKEN,
    build_sensor001g_activation_gate,
)


def sensor001f_decision(*, recommended_decision: str = "activate_controlled_profile", status: str = "decision_ready") -> dict[str, str]:
    return {
        "overall_status": status,
        "recommended_decision": recommended_decision,
        "confidence": "medium",
    }


def review_profile(*, is_active: bool = False, location: str | None = None, radius: int | None = None) -> MarketSensorProfileState:
    return MarketSensorProfileState(
        id=74,
        profile_name=BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
        source_name=BA_SOURCE_NAME,
        search_term="Data Engineer",
        search_location=location,
        search_radius_km=radius,
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


def test_activation_gate_reports_dry_run_ready_without_db_write() -> None:
    report = build_sensor001g_activation_gate(
        sensor001f_report=sensor001f_decision(),
        profiles=(review_profile(),),
        terms=review_terms(),
    ).as_dict()

    assert report["overall_status"] == "activation_apply_ready"
    assert report["activation_target"]["profile_name"] == BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME
    assert report["safety_boundary"]["database_writes"] is False
    assert report["safety_boundary"]["profile_activation_write"] is False


def test_activation_gate_blocks_non_activation_recommendation() -> None:
    report = build_sensor001g_activation_gate(
        sensor001f_report=sensor001f_decision(recommended_decision="keep_review_profile_inactive_and_monitor"),
        profiles=(review_profile(),),
        terms=review_terms(),
    ).as_dict()

    assert report["overall_status"] == "activation_blocked_by_sensor001f_recommendation"
    assert report["activation_target"] is None


def test_activation_gate_blocks_missing_confirmation_on_apply() -> None:
    report = build_sensor001g_activation_gate(
        sensor001f_report=sensor001f_decision(),
        profiles=(review_profile(),),
        terms=review_terms(),
        apply_requested=True,
        confirmation_token=None,
    ).as_dict()

    assert report["overall_status"] == "activation_apply_blocked_by_missing_confirmation"
    assert report["safety_boundary"]["database_writes"] is False


def test_activation_gate_authorizes_apply_only_with_confirmation() -> None:
    report = build_sensor001g_activation_gate(
        sensor001f_report=sensor001f_decision(),
        profiles=(review_profile(),),
        terms=review_terms(),
        apply_requested=True,
        confirmation_token=CONFIRMATION_TOKEN,
    ).as_dict()

    assert report["overall_status"] == "activation_apply_authorized"
    assert report["safety_boundary"]["database_writes"] is False
    assert "authorized" in " ".join(report["findings"])


def test_activation_gate_reports_applied_after_runner_write() -> None:
    report = build_sensor001g_activation_gate(
        sensor001f_report=sensor001f_decision(),
        profiles=(review_profile(is_active=True),),
        terms=review_terms(),
        apply_requested=True,
        confirmation_token=CONFIRMATION_TOKEN,
        apply_executed=True,
    ).as_dict()

    assert report["overall_status"] == "activation_applied"
    assert report["safety_boundary"]["database_writes"] is True


def test_activation_gate_blocks_scope_mismatch() -> None:
    report = build_sensor001g_activation_gate(
        sensor001f_report=sensor001f_decision(),
        profiles=(review_profile(location="30629", radius=50),),
        terms=review_terms(),
    ).as_dict()

    assert report["overall_status"] == "activation_blocked_by_profile_scope_mismatch"


def test_sensor001g_script_is_directly_executable_from_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_sensor001g_ba_remote_controlled_activation_gate.py",
            "--help",
        ],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "SENSOR-001G" in result.stdout
