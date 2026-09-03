from datetime import date, datetime, timezone

from scripts.product_v1_data_layers_runtime import (
    FLOW_DAYS,
    _source_rows,
    build_data_layers_payload,
)


def test_builder_preserves_missing_history_and_current_snapshot_boundary() -> None:
    today = date(2026, 9, 3)
    payload = build_data_layers_payload(
        today=today,
        bronze_count=100,
        silver_count=60,
        gold_assessed_count=30,
        rankable_now=6,
        top_jobs_now=5,
        bronze_flow={today: 8},
        observation_flow=None,
        silver_flow={today: 4},
        gold_flow={today: 2},
        latest_bronze_observation=datetime(2026, 9, 3, 5, 0, tzinfo=timezone.utc),
        latest_silver_normalization=datetime(2026, 9, 3, 5, 5, tzinfo=timezone.utc),
        latest_gold_assessment=datetime(2026, 9, 3, 5, 10, tzinfo=timezone.utc),
        sources=[],
    )

    assert payload["inventory"] == {
        "bronze_jobs": 100,
        "silver_jobs": 60,
        "gold_assessed": 30,
        "rankable_now": 6,
        "top_jobs_now": 5,
    }
    assert payload["coverage"] == {
        "bronze_to_silver_pct": 60.0,
        "silver_to_gold_pct": 50.0,
        "gold_to_rankable_pct": 20.0,
    }
    flow = payload["flow"]
    assert isinstance(flow, list)
    assert len(flow) == FLOW_DAYS
    assert flow[-1] == {
        "date": "2026-09-03",
        "bronze_new": 8,
        "bronze_observations": None,
        "silver_normalized": 4,
        "gold_assessed": 2,
    }
    boundaries = payload["boundaries"]
    assert isinstance(boundaries, dict)
    assert boundaries["read_only"] is True
    assert boundaries["migration_free"] is True
    assert boundaries["creates_telemetry"] is False
    assert boundaries["historical_rankable_series_available"] is False
    assert boundaries["historical_top5_series_available"] is False


def test_builder_uses_null_not_fake_percentage_when_denominator_is_missing() -> None:
    payload = build_data_layers_payload(
        today=date(2026, 9, 3),
        bronze_count=None,
        silver_count=0,
        gold_assessed_count=0,
        rankable_now=0,
        top_jobs_now=0,
        bronze_flow=None,
        observation_flow=None,
        silver_flow={},
        gold_flow={},
        latest_bronze_observation=None,
        latest_silver_normalization=None,
        latest_gold_assessment=None,
        sources=[],
    )

    assert payload["coverage"] == {
        "bronze_to_silver_pct": None,
        "silver_to_gold_pct": None,
        "gold_to_rankable_pct": None,
    }
    flow = payload["flow"]
    assert isinstance(flow, list)
    assert all(point["bronze_new"] is None for point in flow)
    assert all(point["bronze_observations"] is None for point in flow)


def test_source_projection_reuses_existing_source_layer_truth() -> None:
    rows = _source_rows(
        {
            "source_connector_overview": {
                "sources": [
                    {
                        "source_name": "personio:alpha",
                        "source_label": "Alpha",
                        "last_ingestion": {
                            "status": "success",
                            "started_at": "2026-09-03T03:00:00+00:00",
                            "finished_at": "2026-09-03T03:01:00+00:00",
                            "total_loaded": 12,
                            "inserted_count": 7,
                        },
                        "layers": {
                            "status": "bronze_and_silver_present",
                            "bronze_count": 10,
                            "silver_count": 8,
                        },
                    },
                    {
                        "source_name": "personio:beta",
                        "source_label": "Beta",
                        "last_ingestion": {"status": "not_run"},
                        "layers": {"bronze_count": 0, "silver_count": 0},
                    },
                ]
            }
        }
    )

    assert rows[0] == {
        "source_name": "personio:alpha",
        "source_label": "Alpha",
        "last_run_at": "2026-09-03T03:01:00+00:00",
        "last_run_status": "success",
        "loaded": 12,
        "inserted": 7,
        "bronze": 10,
        "silver": 8,
        "layer_status": "bronze_and_silver_present",
    }
    assert rows[1]["source_name"] == "personio:beta"
