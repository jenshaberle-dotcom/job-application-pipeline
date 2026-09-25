from __future__ import annotations

from datetime import UTC, datetime, timedelta

from scripts.run_freeze2_ingestion_stall_diagnostic import _classify


NOW = datetime(2026, 9, 25, 21, 0, tzinfo=UTC)


def test_classifies_missing_recent_runs_as_scheduler_gap() -> None:
    classification, _ = _classify(
        recurring_profile_count=4,
        latest_run={
            "status": "success",
            "started_at": NOW - timedelta(hours=50),
        },
        recent_failed_run_count=0,
        latest_bronze=NOW - timedelta(hours=50),
        latest_silver=NOW - timedelta(hours=50),
        now=NOW,
    )
    assert classification == "scheduler_or_wrapper_not_running"


def test_classifies_recent_failed_run_before_zero_yield() -> None:
    classification, _ = _classify(
        recurring_profile_count=4,
        latest_run={
            "status": "failed",
            "started_at": NOW - timedelta(hours=2),
        },
        recent_failed_run_count=1,
        latest_bronze=NOW - timedelta(hours=48),
        latest_silver=NOW - timedelta(hours=48),
        now=NOW,
    )
    assert classification == "ingestion_latest_run_failed"


def test_classifies_recent_runs_without_bronze_as_zero_yield_or_suppression() -> None:
    classification, _ = _classify(
        recurring_profile_count=4,
        latest_run={
            "status": "success",
            "started_at": NOW - timedelta(hours=2),
        },
        recent_failed_run_count=0,
        latest_bronze=NOW - timedelta(hours=50),
        latest_silver=NOW - timedelta(hours=50),
        now=NOW,
    )
    assert classification == "recent_runs_without_new_bronze"


def test_classifies_pipeline_recent_when_all_layers_are_recent() -> None:
    classification, _ = _classify(
        recurring_profile_count=4,
        latest_run={
            "status": "success",
            "started_at": NOW - timedelta(hours=2),
        },
        recent_failed_run_count=0,
        latest_bronze=NOW - timedelta(hours=3),
        latest_silver=NOW - timedelta(hours=2),
        now=NOW,
    )
    assert classification == "pipeline_recent"
