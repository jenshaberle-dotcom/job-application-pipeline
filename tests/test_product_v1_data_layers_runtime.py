from datetime import date, datetime, timezone

from scripts.product_v1_data_layers_runtime import FLOW_DAYS, build_data_layers_payload


def test_builder_uses_one_current_all_jobs_population() -> None:
    today = date(2026, 9, 16)
    payload = build_data_layers_payload(
        today=today,
        all_jobs=70,
        bronze_count=70,
        silver_count=70,
        gold_assessed_count=69,
        rankable_now=6,
        top_jobs_now=5,
        bronze_flow={today: 8},
        silver_flow={today: 4},
        gold_flow={today: 2},
        latest_bronze_observation=datetime(2026, 9, 16, 5, 0, tzinfo=timezone.utc),
        latest_silver_normalization=datetime(2026, 9, 16, 5, 5, tzinfo=timezone.utc),
        latest_gold_assessment=datetime(2026, 9, 16, 5, 10, tzinfo=timezone.utc),
    )

    assert payload["population"] == {
        "key": "current_all_jobs",
        "label": "Current All jobs",
        "all_jobs": 70,
    }
    assert payload["layers"] == {
        "bronze_jobs": 70,
        "silver_jobs": 70,
        "gold_assessed": 69,
        "rankable_now": 6,
        "top_jobs_now": 5,
    }
    assert payload["coverage"] == {
        "bronze_to_silver_pct": 100.0,
        "silver_to_gold_pct": 98.6,
        "all_jobs_gold_assessed_pct": 98.6,
    }
    flow = payload["flow"]
    assert isinstance(flow, list)
    assert len(flow) == FLOW_DAYS
    assert flow[-1] == {
        "date": "2026-09-16",
        "bronze_new": 8,
        "silver_normalized": 4,
        "gold_assessed": 2,
    }
    boundaries = payload["boundaries"]
    assert boundaries["read_only"] is True
    assert boundaries["single_population_current_all_jobs"] is True
    assert boundaries["historical_inventory_excluded_from_primary_counts"] is True
    assert boundaries["repeat_observations_excluded_from_primary_flow"] is True


def test_builder_uses_null_not_fake_percentage_when_denominator_is_empty() -> None:
    payload = build_data_layers_payload(
        today=date(2026, 9, 16),
        all_jobs=0,
        bronze_count=0,
        silver_count=0,
        gold_assessed_count=0,
        rankable_now=0,
        top_jobs_now=0,
        bronze_flow=None,
        silver_flow={},
        gold_flow={},
        latest_bronze_observation=None,
        latest_silver_normalization=None,
        latest_gold_assessment=None,
    )

    assert payload["coverage"] == {
        "bronze_to_silver_pct": None,
        "silver_to_gold_pct": None,
        "all_jobs_gold_assessed_pct": None,
    }
    flow = payload["flow"]
    assert isinstance(flow, list)
    assert all(point["bronze_new"] is None for point in flow)
    assert all("bronze_observations" not in point for point in flow)
