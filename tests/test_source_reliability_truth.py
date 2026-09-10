from __future__ import annotations

from src.search_intelligence.source_connector_overview import build_source_connector_overview


class FakeConnector:
    pass


class FakeRegistry:
    def __init__(self, roles: dict[str, str], registered: tuple[str, ...] = ()) -> None:
        self.roles = roles
        self._registered = set(registered)
        self.exact_factories = {name: object() for name in registered}

    def create(self, source_name: str) -> object:
        if source_name not in self._registered:
            raise ValueError(f"No connector configured for source: {source_name}")
        return FakeConnector()

    def role_for(self, source_name: str) -> str:
        return self.roles.get(source_name, "unknown")


def _candidate(source_name: str, *, implemented: bool) -> dict[str, object]:
    return {
        "candidate_id": 17,
        "source_name": source_name,
        "company_name": "Example GmbH",
        "source_type": "employer_origin_career_site",
        "candidate_status": "candidate",
        "connector_implemented": implemented,
        "connector_validation_gate_status": "passed",
        "connector_validation_gate_decision": "ready_for_final_approval",
        "final_approval_gate_status": "passed",
        "final_approval_gate_decision": "approve_connector_registration",
    }


def _source(payload: dict[str, object], source_name: str) -> dict[str, object]:
    rows = payload["sources"]
    assert isinstance(rows, list)
    return next(row for row in rows if row["source_name"] == source_name)


def test_unimplemented_candidate_is_inventory_not_attention() -> None:
    source_name = "candidate:example"
    payload = build_source_connector_overview(
        registry=FakeRegistry({source_name: "employer_origin"}),
        candidates=[_candidate(source_name, implemented=False)],
    )

    source = _source(payload, source_name)
    assert source["connector"]["implementation_status"] == "not_implemented"
    assert source["current_blocker"] is None
    assert source["next_action"].startswith("Known source candidate")
    assert payload["summary"]["attention_count"] == 0
    assert payload["boundaries"]["not_implemented_is_inventory_not_attention"] is True


def test_active_employer_origin_exposes_zero_latest_delivery() -> None:
    source_name = "origin:zero"
    payload = build_source_connector_overview(
        registry=FakeRegistry({source_name: "employer_origin"}, (source_name,)),
        candidates=[_candidate(source_name, implemented=True)],
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
                "total_loaded": 0,
                "inserted_count": 0,
            }
        ],
    )

    source = _source(payload, source_name)
    assert source["activation"]["active"] is True
    assert source["activation"]["status"] == "active_last_run_0_jobs"
    assert "latest ingestion loaded 0 jobs" in source["next_action"]
    assert payload["summary"]["active_last_run_zero_count"] == 1
    assert payload["summary"]["active_last_run_loaded_count"] == 0


def test_active_employer_origin_exposes_latest_delivery_count() -> None:
    source_name = "origin:delivering"
    payload = build_source_connector_overview(
        registry=FakeRegistry({source_name: "employer_origin"}, (source_name,)),
        candidates=[_candidate(source_name, implemented=True)],
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
                "total_loaded": 7,
                "inserted_count": 2,
            }
        ],
    )

    source = _source(payload, source_name)
    assert source["activation"]["status"] == "active_last_run_7_jobs"
    assert "latest ingestion loaded 7 jobs and inserted 2" in source["next_action"]
    assert payload["summary"]["active_last_run_loaded_count"] == 1
    assert payload["summary"]["active_last_run_zero_count"] == 0


def test_market_sensor_is_explicitly_not_an_employer_origin_delivery_source() -> None:
    source_name = "sensor:market"
    payload = build_source_connector_overview(
        registry=FakeRegistry({source_name: "sensor"}, (source_name,)),
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
                "total_loaded": 21,
                "inserted_count": 3,
            }
        ],
    )

    source = _source(payload, source_name)
    assert source["activation"]["status"] == "market_sensor_active"
    assert "not Product review jobs" in source["next_action"]
    assert payload["summary"]["sensor_count"] == 1
    assert payload["summary"]["employer_origin_active_count"] == 0
