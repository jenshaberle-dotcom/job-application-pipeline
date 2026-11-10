from __future__ import annotations

import pytest

from scripts.run_current_employer_connector_census import _relation_exists, build_census


def _candidate(
    candidate_id: int,
    key: str,
    *,
    updated_at: str = "2026-09-30T08:00:00+00:00",
    source_name: str | None = None,
) -> dict[str, object]:
    return {
        "id": candidate_id,
        "company_key": key,
        "company_name": key.replace("_", " ").title(),
        "status": "candidate",
        "candidate_url": f"https://{key}.example/jobs",
        "source_name_candidate": source_name or f"candidate:{key}",
        "updated_at": updated_at,
    }


def test_census_excludes_market_sensors_and_partitions_current_candidates() -> None:
    rows = [
        _candidate(1, "alpha"),
        _candidate(2, "beta"),
        _candidate(3, "gamma"),
        _candidate(4, "delta"),
        _candidate(5, "epsilon"),
        _candidate(7, "zeta"),
        _candidate(8, "eta"),
        # Older duplicate candidate identity must not inflate the denominator.
        _candidate(6, "alpha", updated_at="2026-09-01T08:00:00+00:00"),
    ]
    result = build_census(
        candidate_rows=rows,
        active_source_rows=[
            {
                "candidate_id": 1,
                "company_key": "alpha",
                "source_name": "generic_origin:alpha",
                "proof_state": "pass",
            },
            {
                "candidate_id": 2,
                "company_key": "beta",
                "source_name": "generic_origin:beta",
                "proof_state": "pass",
            },
        ],
        profile_rows=[
            {
                "source_name": "generic_origin:alpha",
                "active_profile_count": 1,
                "recurring_profile_count": 1,
            },
            {
                "source_name": "generic_origin:beta",
                "active_profile_count": 1,
                "recurring_profile_count": 0,
            },
        ],
        ingestion_rows=[
            {
                "source_name": "generic_origin:alpha",
                "last_ingestion_status": "success",
            }
        ],
        builder_audit={
            "schema": "jap.deterministic_connector_builder_layer_audit.v6",
            "results": [
                {"company_key": "gamma", "recipe_ready": True},
                {
                    "company_key": "delta",
                    "recipe_ready": False,
                    "first_failure_layer": "inventory",
                },
                {
                    "company_key": "zeta",
                    "recipe_ready": False,
                    "first_failure_layer": "origin",
                },
                {
                    "company_key": "eta",
                    "recipe_ready": False,
                    "first_failure_layer": "proof",
                },
            ]
        },
    )

    summary = result["summary"]
    assert summary["employer_candidate_count"] == 7
    assert summary["market_sensor_count_excluded"] == 7
    assert summary["active_recurring_connector_count"] == 1
    assert summary["connector_materialized_nonrecurring_count"] == 1
    assert summary["recipe_ready_not_materialized_count"] == 1
    assert summary["source_resolution_gap_count"] == 1
    assert summary["capability_gap_count"] == 1
    assert summary["qualification_gap_count"] == 1
    assert summary["resolution_required_count"] == 1
    assert summary["builder_audit_schema"] == (
        "jap.deterministic_connector_builder_layer_audit.v6"
    )
    assert summary["builder_covered_candidate_count"] == 4
    assert summary["builder_unknown_candidate_count"] == 0
    assert summary["builder_population_complete"] is False
    assert {
        row["company_key"]: row["disposition"] for row in result["candidates"]
    } == {
        "alpha": "ACTIVE_RECURRING",
        "beta": "MATERIALIZED_NONRECURRING",
        "gamma": "RECIPE_READY_NOT_MATERIALIZED",
        "delta": "CAPABILITY_GAP",
        "epsilon": "RESOLUTION_REQUIRED",
        "zeta": "SOURCE_RESOLUTION_GAP",
        "eta": "QUALIFICATION_GAP",
    }


def test_failed_recurring_connector_is_still_in_active_denominator() -> None:
    result = build_census(
        candidate_rows=[_candidate(1, "alpha")],
        active_source_rows=[
            {
                "candidate_id": 1,
                "company_key": "alpha",
                "source_name": "generic_origin:alpha",
                "proof_state": "pass",
            }
        ],
        profile_rows=[
            {
                "source_name": "generic_origin:alpha",
                "active_profile_count": 1,
                "recurring_profile_count": 1,
            }
        ],
        ingestion_rows=[
            {
                "source_name": "generic_origin:alpha",
                "last_ingestion_status": "failed",
            }
        ],
    )
    assert result["summary"]["active_recurring_connector_count"] == 1
    assert result["summary"]["broken_active_connector_count"] == 1
    assert result["candidates"][0]["disposition"] == "BROKEN_ACTIVE_CONNECTOR"


def test_missing_builder_audit_does_not_invent_capability_gap() -> None:
    result = build_census(candidate_rows=[_candidate(1, "alpha")])
    assert result["summary"]["capability_gap_count"] == 0
    assert result["summary"]["resolution_required_count"] == 1
    assert result["candidates"][0]["builder_state"] == "NOT_MEASURED"


def test_sensor_family_in_candidate_population_fails_closed() -> None:
    with pytest.raises(
        ValueError,
        match="market_sensor_leaked_into_employer_candidate_population",
    ):
        build_census(
            candidate_rows=[
                _candidate(
                    1,
                    "sensor_leak",
                    source_name="stepstone",
                )
            ]
        )


def test_v6_results_shape_is_consumed_without_inventing_capability_gap() -> None:
    result = build_census(
        candidate_rows=[_candidate(1, "alpha"), _candidate(2, "beta")],
        builder_audit={
            "schema": "jap.deterministic_connector_builder_layer_audit.v6",
            "results": [
                {
                    "company_key": "alpha",
                    "recipe_ready": False,
                    "first_failure_layer": "origin_reachability",
                },
                {
                    "company_key": "beta",
                    "recipe_ready": False,
                    "first_failure_layer": "detail",
                },
            ],
        },
    )
    dispositions = {
        row["company_key"]: row["disposition"] for row in result["candidates"]
    }
    assert dispositions == {
        "alpha": "SOURCE_RESOLUTION_GAP",
        "beta": "CAPABILITY_GAP",
    }
    assert result["summary"]["source_resolution_gap_count"] == 1
    assert result["summary"]["capability_gap_count"] == 1


def test_prefixed_market_sensor_source_identity_fails_closed() -> None:
    with pytest.raises(
        ValueError,
        match="market_sensor_leaked_into_employer_candidate_population",
    ):
        build_census(
            candidate_rows=[
                _candidate(
                    1,
                    "sensor_leak",
                    source_name="market_sensor:stepstone",
                )
            ]
        )


def test_relation_exists_accepts_dict_row_cursor() -> None:
    class Cursor:
        def __init__(self, value):
            self.value = value
            self.executed = None

        def execute(self, query, params):
            self.executed = (query, params)

        def fetchone(self):
            return {"relation_name": self.value}

    present = Cursor("generic_employer_origin_active_sources")
    missing = Cursor(None)
    assert _relation_exists(present, "generic_employer_origin_active_sources") is True
    assert _relation_exists(missing, "generic_employer_origin_active_sources") is False
    assert "AS relation_name" in present.executed[0]


def test_builder_coverage_reports_complete_and_unknown_rows() -> None:
    result = build_census(
        candidate_rows=[_candidate(1, "alpha")],
        builder_audit={
            "schema": "jap.deterministic_connector_builder_layer_audit.v6",
            "results": [
                {"company_key": "alpha", "recipe_ready": True},
                {"company_key": "stale_candidate", "recipe_ready": True},
            ],
        },
    )
    summary = result["summary"]
    assert summary["builder_covered_candidate_count"] == 1
    assert summary["builder_unknown_candidate_count"] == 1
    assert summary["builder_population_complete"] is True
