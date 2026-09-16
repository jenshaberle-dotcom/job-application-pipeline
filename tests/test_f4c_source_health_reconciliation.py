from datetime import datetime, timezone

import pytest

from scripts.run_f4c_source_health_reconciliation import (
    ReconciliationStop,
    reconcile,
    surface_contract_evidence,
)


def _source(
    name: str,
    *,
    active: bool = True,
    run_status: str = "success",
    operational_health: str = "healthy",
    loaded: int = 3,
) -> dict[str, object]:
    return {
        "candidate_id": 1,
        "source_name": name,
        "source_label": name,
        "source_role": "employer_origin",
        "candidate_status": "active_controlled",
        "activation": {"active": active, "status": "active" if active else "not_activated"},
        "search_profiles": {"active_profile_count": 1 if active else 0},
        "operational_health": {
            "status": operational_health,
            "latest_run_status": run_status,
            "truth_source": "ingestion_runs",
        },
        "last_ingestion": {
            "status": run_status,
            "started_at": "2026-09-10T09:00:00+00:00",
            "finished_at": "2026-09-10T09:10:00+00:00",
            "total_loaded": loaded,
            "inserted_count": loaded,
        },
        "layers": {
            "bronze_count": loaded,
            "silver_count": loaded,
            "status": "bronze_and_silver_present" if loaded else "no_ingestion",
        },
        "current_blocker": None,
        "next_action": "Monitor",
    }


def _payload(*sources: dict[str, object]) -> dict[str, object]:
    return {
        "source_connector_overview": {
            "summary": {"source_count": len(sources)},
            "sources": list(sources),
        }
    }


def test_historical_success_is_measured_not_promoted_to_current_health_authority() -> None:
    observed_at = datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)
    report = reconcile(
        _payload(_source("generic_origin:example")),
        recurring_profiles={
            "generic_origin:example": {
                "profile_count": 1,
                "active_profile_count": 1,
                "recurring_enabled_profile_count": 1,
            }
        },
        source_sha="a" * 40,
        observed_at=observed_at,
        surface_evidence={
            "operations_reuses_source_lifecycle_summary": True,
            "data_layers_has_per_source_last_run_projection": True,
        },
    )

    row = report["rows"][0]
    assert row["product_operational_health"] == "healthy"
    assert row["latest_run_status"] == "success"
    assert row["last_run_age_hours"] == pytest.approx(143.83, abs=0.01)
    assert row["explicit_cadence_authority"] == "not_projected"
    assert (
        row["current_health_claim_support"]
        == "historical_run_success_only_no_cadence_freshness_authority"
    )
    assert row["current_reachability"] == "unknown_not_measured_by_source_overview"
    assert report["summary"]["latest_success_rendered_healthy_count"] == 1
    assert report["summary"]["healthy_without_explicit_cadence_freshness_authority_count"] == 1


def test_recurring_eligibility_is_not_treated_as_cadence() -> None:
    report = reconcile(
        _payload(_source("generic_origin:manual", loaded=0)),
        recurring_profiles={
            "generic_origin:manual": {
                "profile_count": 1,
                "active_profile_count": 1,
                "recurring_enabled_profile_count": 0,
            }
        },
        source_sha="b" * 40,
        observed_at=datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc),
        surface_evidence={},
    )
    row = report["rows"][0]
    assert row["recurring_ingestion_eligible"] is False
    assert row["explicit_cadence_authority"] == "not_projected"
    assert row["delivery"]["active_zero_last_run_delivery"] is True
    assert report["boundaries"]["recurring_eligibility_is_not_cadence"] is True
    assert report["summary"]["active_zero_last_run_delivery_count"] == 1


def test_failed_run_does_not_get_diagnostic_healthy_claim() -> None:
    report = reconcile(
        _payload(
            _source(
                "generic_origin:failed",
                run_status="failed",
                operational_health="failed",
                loaded=0,
            )
        ),
        recurring_profiles={},
        source_sha="c" * 40,
        observed_at=datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc),
        surface_evidence={},
    )
    row = report["rows"][0]
    assert row["healthy_from_latest_success"] is False
    assert row["current_health_claim_support"] == "no_current_healthy_claim"
    assert report["summary"]["latest_success_rendered_healthy_count"] == 0


def test_empty_or_invalid_source_overview_fails_closed() -> None:
    with pytest.raises(ReconciliationStop, match="SOURCE_CONNECTOR_ROWS_EMPTY"):
        reconcile(
            _payload(),
            recurring_profiles={},
            source_sha="d" * 40,
            observed_at=datetime.now(timezone.utc),
            surface_evidence={},
        )


def test_current_frontend_contract_confirms_f4c_surface_consolidation() -> None:
    evidence = surface_contract_evidence()
    assert evidence["active_workspace"] is True
    assert evidence["sources_owns_source_connector_overview"] is True
    # Legacy Operations implementation remains in the workspace source for now,
    # but F4C removes it from the top-level operator navigation.
    assert evidence["operations_reuses_source_lifecycle_summary"] is True
    assert evidence["operations_top_level_hidden"] is True
    # Data Layers must no longer compete with Sources for per-source run status.
    assert evidence["data_layers_has_per_source_last_run_projection"] is False
    assert evidence["data_layers_owns_bronze_silver_gold_flow"] is True
    assert evidence["data_layers_separates_persisted_and_current_scope"] is True
