from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from scripts.product_v1_f4c_source_health_runtime import project_current_source_health


NOW = datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)


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
                    "source_name": "generic_origin:example",
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


def source(result: dict[str, object]) -> dict[str, object]:
    overview = result["source_connector_overview"]
    assert isinstance(overview, dict)
    rows = overview["sources"]
    assert isinstance(rows, list)
    row = rows[0]
    assert isinstance(row, dict)
    return row


def test_historical_success_without_cadence_is_not_current_healthy() -> None:
    result = project_current_source_health(
        payload_for(),
        schedule_evidence={
            "generic_origin:example": {
                "recurring_enabled_profile_count": 1,
                "expected_cadence_minutes": None,
                "cadence_truth_source": None,
            }
        },
        observed_at=NOW,
    )

    row = source(result)
    health = row["operational_health"]
    assert health["historical_projection_status"] == "healthy"
    assert health["latest_run_status"] == "success"
    assert health["status"] == "unknown"
    assert health["reason"] == "successful_run_without_explicit_cadence_authority"
    assert row["scheduling"]["status"] == "recurring_enabled_cadence_unknown"
    assert row["scheduling"]["cadence_authority"] is False


def test_explicit_cadence_can_prove_current_healthy() -> None:
    result = project_current_source_health(
        payload_for(finished_at="2026-09-16T08:30:00+00:00"),
        schedule_evidence={
            "generic_origin:example": {
                "recurring_enabled_profile_count": 1,
                "expected_cadence_minutes": 120,
                "cadence_truth_source": "verified_scheduler_policy",
            }
        },
        observed_at=NOW,
    )

    row = source(result)
    assert row["operational_health"]["status"] == "healthy"
    assert row["operational_health"]["freshness_status"] == "within_cadence"
    assert row["scheduling"]["next_expected_run_at"] == "2026-09-16T10:30:00+00:00"


def test_explicit_cadence_marks_overdue_success_stale() -> None:
    result = project_current_source_health(
        payload_for(finished_at="2026-09-16T04:00:00+00:00"),
        schedule_evidence={
            "generic_origin:example": {
                "recurring_enabled_profile_count": 1,
                "expected_cadence_minutes": 120,
                "cadence_truth_source": "verified_scheduler_policy",
            }
        },
        observed_at=NOW,
    )

    row = source(result)
    assert row["operational_health"]["status"] == "stale"
    assert row["operational_health"]["reason"] == (
        "successful_run_overdue_for_explicit_cadence"
    )
    assert row["operational_health"]["freshness_status"] == "overdue"


def test_latest_failed_attempt_is_degraded_without_inventing_cadence() -> None:
    result = project_current_source_health(
        payload_for(latest_status="failed", historical_health="failed", loaded=0, inserted=0),
        schedule_evidence={
            "generic_origin:example": {
                "recurring_enabled_profile_count": 1,
                "expected_cadence_minutes": None,
                "cadence_truth_source": None,
            }
        },
        observed_at=NOW,
    )

    row = source(result)
    assert row["operational_health"]["status"] == "degraded"
    assert row["operational_health"]["reason"] == "latest_attempt_failed"
    assert row["reachability"]["status"] == "unknown"


def test_zero_yield_success_stays_delivery_truth_not_health_failure() -> None:
    result = project_current_source_health(
        payload_for(loaded=0, inserted=0),
        schedule_evidence={
            "generic_origin:example": {
                "recurring_enabled_profile_count": 1,
                "expected_cadence_minutes": None,
                "cadence_truth_source": None,
            }
        },
        observed_at=NOW,
    )

    row = source(result)
    assert row["delivery"]["latest_success_zero_yield"] is True
    assert row["operational_health"]["status"] == "unknown"
    assert row["operational_health"]["reason"] != "latest_attempt_failed"


def test_no_schedule_evidence_remains_unknown_not_scheduled_by_inference() -> None:
    result = project_current_source_health(
        payload_for(),
        schedule_evidence={},
        observed_at=NOW,
    )

    row = source(result)
    assert row["scheduling"]["status"] == "unknown"
    assert row["scheduling"]["recurring_ingestion_eligible"] is None
    assert row["operational_health"]["status"] == "unknown"


def test_projection_is_read_only_and_publishes_summary_boundaries() -> None:
    original = payload_for(loaded=0, inserted=0)
    before = deepcopy(original)
    result = project_current_source_health(
        original,
        schedule_evidence={
            "generic_origin:example": {
                "recurring_enabled_profile_count": 1,
                "expected_cadence_minutes": None,
                "cadence_truth_source": None,
            }
        },
        observed_at=NOW,
    )

    assert original == before
    overview = result["source_connector_overview"]
    assert overview["summary"]["latest_success_without_cadence_authority_count"] == 1
    assert overview["summary"]["latest_success_zero_yield_count"] == 1
    assert overview["summary"]["current_health_unknown_count"] == 1
    assert result["boundaries"]["historical_run_success_is_not_current_source_health"] is True
    assert result["boundaries"]["zero_yield_is_not_source_failure"] is True
    assert result["boundaries"]["current_reachability_requires_current_measurement"] is True
