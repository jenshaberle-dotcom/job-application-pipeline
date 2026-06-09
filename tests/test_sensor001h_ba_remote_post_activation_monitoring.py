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
from src.search_intelligence.sensor001h_ba_remote_post_activation_monitoring import (
    build_sensor001h_post_activation_monitoring,
)


def sensor001g_report(status: str = "already_active_controlled_profile") -> dict[str, str]:
    return {"overall_status": status}


def review_profile(*, is_active: bool = True) -> MarketSensorProfileState:
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


def review_terms(*, omit: str | None = None) -> tuple[MarketSensorTermState, ...]:
    return tuple(
        MarketSensorTermState(
            profile_name=BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
            search_term=term,
            is_active=True,
        )
        for term in EXPECTED_BA_REMOTE_TERMS
        if term != omit
    )


def term_rows_with_no_runs() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "search_term": term,
            "ingestion_run_count": 0,
            "raw_jobs_count": 0,
            "total_loaded": 0,
            "inserted_count": 0,
            "duplicate_count": 0,
            "failed_run_count": 0,
            "latest_started_at": None,
        }
        for term in EXPECTED_BA_REMOTE_TERMS
    )


def test_monitoring_reports_ready_awaiting_first_run_for_active_profile() -> None:
    report = build_sensor001h_post_activation_monitoring(
        sensor001g_report=sensor001g_report(),
        profiles=(review_profile(),),
        terms=review_terms(),
        term_observation_rows=term_rows_with_no_runs(),
        latest_run_rows=(),
    ).as_dict()

    assert report["overall_status"] == "monitoring_ready_awaiting_first_run"
    assert report["activation_state"]["current_is_active"] is True
    assert report["metric_summary"]["ingestion_run_count"] == 0
    assert report["safety_boundary"]["database_writes"] is False
    assert report["safety_boundary"]["external_requests"] is False


def test_monitoring_blocks_until_sensor001g_confirms_activation() -> None:
    report = build_sensor001h_post_activation_monitoring(
        sensor001g_report=sensor001g_report("activation_apply_ready"),
        profiles=(review_profile(is_active=False),),
        terms=review_terms(),
        term_observation_rows=term_rows_with_no_runs(),
        latest_run_rows=(),
    ).as_dict()

    assert report["overall_status"] == "monitoring_blocked_until_activation_confirmed"


def test_monitoring_blocks_if_profile_not_active_in_database() -> None:
    report = build_sensor001h_post_activation_monitoring(
        sensor001g_report=sensor001g_report(),
        profiles=(review_profile(is_active=False),),
        terms=review_terms(),
        term_observation_rows=term_rows_with_no_runs(),
        latest_run_rows=(),
    ).as_dict()

    assert report["overall_status"] == "monitoring_blocked_profile_not_active"


def test_monitoring_detects_missing_expected_terms() -> None:
    report = build_sensor001h_post_activation_monitoring(
        sensor001g_report=sensor001g_report(),
        profiles=(review_profile(),),
        terms=review_terms(omit="ETL"),
        term_observation_rows=term_rows_with_no_runs(),
        latest_run_rows=(),
    ).as_dict()

    assert report["overall_status"] == "monitoring_attention_required_configuration_gap"
    assert "ETL" in report["activation_state"]["missing_expected_terms"]


def test_monitoring_detects_failed_runs() -> None:
    rows = (
        {
            "search_term": "Data Engineer",
            "ingestion_run_count": 1,
            "raw_jobs_count": 0,
            "total_loaded": 0,
            "inserted_count": 0,
            "duplicate_count": 0,
            "failed_run_count": 1,
            "latest_started_at": "2026-06-09 08:00:00+00",
        },
    )
    latest_runs = (
        {
            "id": 42,
            "status": "failed",
            "search_term": "Data Engineer",
            "total_loaded": 0,
            "inserted_count": 0,
            "duplicate_count": 0,
            "error_type": "RuntimeError",
            "error_stage": "fetch",
            "error_message": "boom",
            "started_at": "2026-06-09 08:00:00+00",
            "finished_at": "2026-06-09 08:00:01+00",
        },
    )

    report = build_sensor001h_post_activation_monitoring(
        sensor001g_report=sensor001g_report(),
        profiles=(review_profile(),),
        terms=review_terms(),
        term_observation_rows=rows,
        latest_run_rows=latest_runs,
    ).as_dict()

    assert report["overall_status"] == "monitoring_attention_required_failed_runs"
    assert report["metric_summary"]["failed_run_count"] == 1


def test_monitoring_reports_observed_runs() -> None:
    rows = (
        {
            "search_term": "Data Engineer",
            "ingestion_run_count": 1,
            "raw_jobs_count": 8,
            "total_loaded": 10,
            "inserted_count": 8,
            "duplicate_count": 2,
            "failed_run_count": 0,
            "latest_started_at": "2026-06-09 08:00:00+00",
        },
    )
    latest_runs = (
        {
            "id": 41,
            "status": "success",
            "search_term": "Data Engineer",
            "total_loaded": 10,
            "inserted_count": 8,
            "duplicate_count": 2,
            "error_type": None,
            "error_stage": None,
            "error_message": None,
            "started_at": "2026-06-09 08:00:00+00",
            "finished_at": "2026-06-09 08:00:02+00",
        },
    )

    report = build_sensor001h_post_activation_monitoring(
        sensor001g_report=sensor001g_report(),
        profiles=(review_profile(),),
        terms=review_terms(),
        term_observation_rows=rows,
        latest_run_rows=latest_runs,
    ).as_dict()

    assert report["overall_status"] == "monitoring_ready_with_observed_runs"
    assert report["metric_summary"]["inserted_count"] == 8


def test_sensor001h_script_is_directly_executable_from_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_sensor001h_ba_remote_post_activation_monitoring.py",
            "--help",
        ],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "SENSOR-001H" in result.stdout
