from __future__ import annotations

from src.connectors.registry import build_default_connector_registry
from src.search_intelligence.source_connector_overview import build_source_connector_overview


def _source(payload: dict[str, object], source_name: str) -> dict[str, object]:
    sources = payload["sources"]
    assert isinstance(sources, list)
    return next(row for row in sources if row["source_name"] == source_name)


def test_ba_sensor_does_not_require_employer_origin_candidate_gates() -> None:
    source_name = "bundesagentur_fuer_arbeit"
    payload = build_source_connector_overview(
        registry=build_default_connector_registry(),
        search_profiles=[
            {
                "source_name": source_name,
                "profile_count": 2,
                "active_profile_count": 2,
                "active_search_term_count": 4,
            }
        ],
        ingestion_runs=[
            {
                "source_name": source_name,
                "last_ingestion_status": "success",
                "total_loaded": 20,
                "inserted_count": 3,
            }
        ],
        layer_presence=[
            {"source_name": source_name, "bronze_count": 120, "silver_count": 80}
        ],
    )

    source = _source(payload, source_name)
    assert source["source_role"] == "sensor"
    assert source["source_type"] == "market_sensor"
    assert source["gates"]["connector_validation_gate"] == {
        "status": "not_applicable",
        "decision": None,
        "passed": True,
        "required": False,
        "truth_source": "connector_registry.source_role",
    }
    assert source["gates"]["final_approval_gate"]["status"] == "not_applicable"
    assert source["lifecycle"]["validation"] == "not_applicable"
    assert source["lifecycle"]["final_approval"] == "not_applicable"
    assert source["operational_health"]["status"] == "healthy"
    assert source["current_blocker"] is None
    assert payload["summary"]["sensor_count"] >= 1
    assert payload["summary"]["healthy_sensor_count"] >= 1


def test_failed_latest_sensor_run_is_attention_even_with_historical_layers() -> None:
    source_name = "bundesagentur_fuer_arbeit"
    payload = build_source_connector_overview(
        registry=build_default_connector_registry(),
        search_profiles=[
            {
                "source_name": source_name,
                "profile_count": 1,
                "active_profile_count": 1,
                "active_search_term_count": 2,
            }
        ],
        ingestion_runs=[
            {
                "source_name": source_name,
                "last_ingestion_status": "failed",
                "total_loaded": 0,
                "inserted_count": 0,
                "error_message": "HTTP 503",
            }
        ],
        layer_presence=[
            {"source_name": source_name, "bronze_count": 50, "silver_count": 40}
        ],
    )

    source = _source(payload, source_name)
    assert source["operational_health"]["status"] == "failed"
    assert source["current_blocker"] == "market_sensor_latest_run_failed"
    assert source["next_action"] == (
        "Run a bounded live sensor probe and resolve the latest ingestion failure"
    )
    assert source["last_ingestion"]["error_message"] == "HTTP 503"


def test_employer_origin_source_still_requires_candidate_gates() -> None:
    source_name = "personio:eraneos"
    payload = build_source_connector_overview(
        registry=build_default_connector_registry(),
        search_profiles=[
            {
                "source_name": source_name,
                "profile_count": 1,
                "active_profile_count": 1,
                "active_search_term_count": 1,
            }
        ],
        ingestion_runs=[
            {
                "source_name": source_name,
                "last_ingestion_status": "success",
                "total_loaded": 12,
                "inserted_count": 2,
            }
        ],
        layer_presence=[
            {"source_name": source_name, "bronze_count": 12, "silver_count": 10}
        ],
    )

    source = _source(payload, source_name)
    assert source["source_role"] == "employer_origin"
    assert source["gates"]["connector_validation_gate"]["required"] is True
    assert source["gates"]["connector_validation_gate"]["passed"] is False
    assert source["current_blocker"] == "active_source_without_proven_validation_gate"
