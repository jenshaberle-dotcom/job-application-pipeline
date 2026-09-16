from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from scripts.product_v1_f4c_source_health_runtime import project_current_source_health


NOW = datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)
SOURCE = "generic_origin:example"


def payload_for(
    *,
    latest_status: str = "success",
    historical_health: str = "healthy",
    finished_at: str | None = "2026-09-16T08:00:00+00:00",
    loaded: int = 4,
    inserted: int = 1,
) -> dict[str, object]:
    return {
        "source_connector_overview": {
            "summary": {"source_count": 1},
            "sources": [
                {
                    "source_name": SOURCE,
                    "source_role": "employer_origin",
                    "operational_health": {
                        "status": historical_health,
                        "latest_run_status": latest_status,
                        "truth_available": True,
                    },
                    "last_ingestion": {
                        "status": latest_status,
                        "finished_at": finished_at,
                        "started_at": finished_at,
                        "total_loaded": loaded,
                        "inserted_count": inserted,
                    },
                }
            ],
        },
        "boundaries": {},
    }


def operator_evidence(**overrides: object) -> dict[str, dict[str, object]]:
    row: dict[str, object] = {
        "current_job_count": 3,
        "last_job_delivery_at": "2026-09-16T08:00:00+00:00",
        "last_job_delivery_loaded": 4,
        "last_job_delivery_inserted": 1,
        "latest_job_observed_at": "2026-09-16T08:30:00+00:00",
        "disappeared_comparison_available": True,
        "disappeared_since_previous_success": 2,
        "previous_successful_execution_at": "2026-09-15T08:00:00+00:00",
        "current_successful_execution_at": "2026-09-16T08:00:00+00:00",
    }
    row.update(overrides)
    return {SOURCE: row}


def source(result: dict[str, object]) -> dict[str, object]:
    overview = result["source_connector_overview"]
    assert isinstance(overview, dict)
    rows = overview["sources"]
    assert isinstance(rows, list)
    row = rows[0]
    assert isinstance(row, dict)
    return row


def test_operator_surface_separates_scan_from_live_reachability() -> None:
    result = project_current_source_health(
        payload_for(),
        schedule_evidence={SOURCE: {"recurring_enabled_profile_count": 1}},
        operator_evidence=operator_evidence(),
        observed_at=NOW,
    )

    row = source(result)
    assert row["source_scan"] == {
        "status": "ok",
        "reason": "latest_source_scan_succeeded",
        "result": "success",
        "finished_at": "2026-09-16T08:00:00+00:00",
        "truth_source": "ingestion_runs",
    }
    assert row["reachability"]["status"] == "not_checked"
    assert row["reachability"]["reason"] == "no_live_source_check_recorded"


def test_operator_delivery_answers_current_jobs_age_and_disappearance() -> None:
    result = project_current_source_health(
        payload_for(),
        schedule_evidence={SOURCE: {"recurring_enabled_profile_count": 1}},
        operator_evidence=operator_evidence(),
        observed_at=NOW,
    )

    delivery = source(result)["delivery"]
    assert delivery["current_job_count"] == 3
    assert delivery["last_job_delivery_at"] == "2026-09-16T08:00:00+00:00"
    assert delivery["latest_job_observed_at"] == "2026-09-16T08:30:00+00:00"
    assert delivery["source_data_age_hours"] == 0.5
    assert delivery["disappeared_comparison_available"] is True
    assert delivery["disappeared_since_previous_success"] == 2


def test_disappearance_stays_unknown_without_two_comparable_successful_executions() -> None:
    result = project_current_source_health(
        payload_for(),
        schedule_evidence={},
        operator_evidence=operator_evidence(
            disappeared_comparison_available=False,
            disappeared_since_previous_success=None,
            disappeared_comparison_reason="two_successful_correlated_executions_required",
        ),
        observed_at=NOW,
    )

    delivery = source(result)["delivery"]
    assert delivery["disappeared_comparison_available"] is False
    assert delivery["disappeared_since_previous_success"] is None


def test_historical_success_without_cadence_is_not_internal_current_healthy() -> None:
    result = project_current_source_health(
        payload_for(),
        schedule_evidence={
            SOURCE: {
                "recurring_enabled_profile_count": 1,
                "expected_cadence_minutes": None,
                "cadence_truth_source": None,
            }
        },
        operator_evidence=operator_evidence(),
        observed_at=NOW,
    )

    row = source(result)
    health = row["operational_health"]
    assert health["historical_projection_status"] == "healthy"
    assert health["latest_run_status"] == "success"
    assert health["status"] == "unknown"
    assert row["source_scan"]["status"] == "ok"
    assert row["scheduling"]["status"] == "recurring_enabled_cadence_unknown"


def test_latest_failed_attempt_is_scan_failure_without_live_reachability_claim() -> None:
    result = project_current_source_health(
        payload_for(latest_status="failed", historical_health="failed", loaded=0, inserted=0),
        schedule_evidence={SOURCE: {"recurring_enabled_profile_count": 1}},
        operator_evidence=operator_evidence(),
        observed_at=NOW,
    )

    row = source(result)
    assert row["source_scan"]["status"] == "failed"
    assert row["operational_health"]["status"] == "degraded"
    assert row["reachability"]["status"] == "not_checked"


def test_zero_yield_success_stays_successful_scan_not_failure() -> None:
    result = project_current_source_health(
        payload_for(loaded=0, inserted=0),
        schedule_evidence={SOURCE: {"recurring_enabled_profile_count": 1}},
        operator_evidence=operator_evidence(),
        observed_at=NOW,
    )

    row = source(result)
    assert row["delivery"]["latest_success_zero_yield"] is True
    assert row["source_scan"]["status"] == "ok"
    assert row["source_scan"]["status"] != "failed"


def test_projection_is_read_only_and_publishes_operator_boundaries() -> None:
    original = payload_for(loaded=0, inserted=0)
    before = deepcopy(original)
    result = project_current_source_health(
        original,
        schedule_evidence={SOURCE: {"recurring_enabled_profile_count": 1}},
        operator_evidence=operator_evidence(),
        observed_at=NOW,
    )

    assert original == before
    overview = result["source_connector_overview"]
    assert overview["summary"]["latest_scan_ok_count"] == 1
    assert overview["summary"]["latest_success_zero_yield_count"] == 1
    assert overview["summary"]["reachability_not_checked_count"] == 1
    assert overview["summary"]["disappeared_comparable_source_count"] == 1
    boundaries = result["boundaries"]
    assert boundaries["historical_run_success_is_not_current_source_health"] is True
    assert boundaries["source_scan_result_is_not_live_reachability"] is True
    assert boundaries["disappeared_count_requires_two_successful_correlated_executions"] is True
