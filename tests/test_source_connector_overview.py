from __future__ import annotations

from copy import deepcopy

from src.connectors.registry import build_default_connector_registry
from src.search_intelligence.source_connector_overview import (
    SCHEMA_VERSION,
    build_source_connector_overview,
)


class FakeConnector:
    pass


class FakeRegistry:
    def __init__(self, registered: tuple[str, ...] = ()) -> None:
        self.exact_factories = {source_name: object() for source_name in registered}
        self._registered = set(registered)

    def create(self, source_name: str) -> object:
        if source_name not in self._registered:
            raise ValueError(f"No connector configured for source: {source_name}")
        return FakeConnector()


def approved_candidate(source_name: str, company_name: str) -> dict[str, object]:
    return {
        "candidate_id": 1,
        "source_name": source_name,
        "company_name": company_name,
        "source_type": "employer_origin_career_site",
        "candidate_status": "connector_candidate",
        "connector_implemented": True,
        "connector_validation_gate_status": "passed",
        "connector_validation_gate_decision": "ready_for_final_approval",
        "final_approval_gate_status": "passed",
        "final_approval_gate_decision": "approve_connector_registration",
    }


def source_by_name(payload: dict[str, object], source_name: str) -> dict[str, object]:
    sources = payload["sources"]
    assert isinstance(sources, list)
    return next(source for source in sources if source["source_name"] == source_name)


def test_accompio_and_computacenter_are_registered_but_not_activated_or_ingested() -> None:
    payload = build_source_connector_overview(
        registry=build_default_connector_registry(),
        candidates=[
            approved_candidate("accompio:discovery", "accompio GmbH"),
            approved_candidate("computacenter:discovery", "Computacenter AG & Co. oHG"),
        ],
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    for source_name in ("accompio:discovery", "computacenter:discovery"):
        source = source_by_name(payload, source_name)
        assert source["connector"]["implemented"] is True
        assert source["connector"]["code_backed_registered"] is True
        assert source["gates"]["connector_validation_gate"]["passed"] is True
        assert source["gates"]["final_approval_gate"]["passed"] is True
        assert source["activation"]["status"] == "not_activated"
        assert source["search_profiles"]["status"] == "not_configured"
        assert source["last_ingestion"]["status"] == "not_run"
        assert source["layers"]["status"] == "no_ingestion"
        assert source["lifecycle"] == {
            "implementation": "implemented",
            "validation": "passed",
            "final_approval": "approved",
            "registration": "registered",
            "activation": "not_activated",
            "ingestion": "not_ingested",
        }
        assert source["current_blocker"] == "controlled_activation_not_completed"


def test_active_source_reports_search_profiles_ingestion_and_layers_separately() -> None:
    source_name = "active:source"
    payload = build_source_connector_overview(
        registry=FakeRegistry((source_name,)),
        candidates=[approved_candidate(source_name, "Active Source")],
        search_profiles=[
            {
                "source_name": source_name,
                "profile_count": 2,
                "active_profile_count": 2,
                "active_search_term_count": 7,
            }
        ],
        ingestion_runs=[
            {
                "source_name": source_name,
                "last_ingestion_status": "success",
                "total_loaded": 9,
                "inserted_count": 7,
            }
        ],
        layer_presence=[
            {"source_name": source_name, "bronze_count": 7, "silver_count": 5}
        ],
    )

    source = source_by_name(payload, source_name)
    assert source["activation"]["active"] is True
    assert source["search_profiles"]["status"] == "active"
    assert source["last_ingestion"]["status"] == "success"
    assert source["layers"]["status"] == "bronze_and_silver_present"
    assert source["lifecycle"]["ingestion"] == "ingested"
    assert source["current_blocker"] is None


def test_validated_implemented_connector_can_remain_unregistered() -> None:
    source_name = "candidate:unregistered"
    payload = build_source_connector_overview(
        registry=FakeRegistry(),
        candidates=[approved_candidate(source_name, "Unregistered Candidate")],
    )

    source = source_by_name(payload, source_name)
    assert source["connector"]["implemented"] is True
    assert source["connector"]["code_backed_registered"] is False
    assert source["activation"]["active"] is False
    assert source["current_blocker"] == "connector_not_registered"
    assert source["next_action"] == "Register the connector in code"


def test_registered_source_is_not_implicitly_active() -> None:
    source_name = "registered:only"
    payload = build_source_connector_overview(
        registry=FakeRegistry((source_name,)),
        candidates=[approved_candidate(source_name, "Registered Only")],
    )

    source = source_by_name(payload, source_name)
    assert source["connector"]["code_backed_registered"] is True
    assert source["activation"]["status"] == "not_activated"
    assert source["layers"]["status"] == "no_ingestion"


def test_unknown_active_source_is_flagged_instead_of_optimistically_completed() -> None:
    source_name = "unknown:active"
    payload = build_source_connector_overview(
        registry=FakeRegistry(),
        search_profiles=[
            {
                "source_name": source_name,
                "profile_count": 1,
                "active_profile_count": 1,
                "active_search_term_count": 0,
            }
        ],
    )

    source = source_by_name(payload, source_name)
    assert source["gates"]["connector_validation_gate"]["status"] == "unknown"
    assert "active_source_without_code_backed_registration" in source["inconsistencies"]
    assert source["current_blocker"] == "active_source_without_code_backed_registration"
    assert payload["summary"]["attention_count"] >= 1


def test_overview_assembly_does_not_mutate_input_rows() -> None:
    candidates = [approved_candidate("stable:source", "Stable Source")]
    profiles = [
        {
            "source_name": "stable:source",
            "profile_count": 0,
            "active_profile_count": 0,
        }
    ]
    before = deepcopy((candidates, profiles))

    build_source_connector_overview(
        registry=FakeRegistry(("stable:source",)),
        candidates=candidates,
        search_profiles=profiles,
    )

    assert (candidates, profiles) == before


def test_unavailable_runtime_truth_is_unknown_not_optimistically_absent() -> None:
    source_name = "registered:truth-gap"
    payload = build_source_connector_overview(
        registry=FakeRegistry((source_name,)),
        candidates=[approved_candidate(source_name, "Truth Gap")],
        truth_availability={
            "search_profiles": False,
            "ingestion_runs": False,
            "raw_jobs": False,
            "silver_jobs": False,
        },
    )

    source = source_by_name(payload, source_name)
    assert source["activation"]["status"] == "unknown"
    assert source["search_profiles"]["status"] == "unknown"
    assert source["last_ingestion"]["status"] == "unknown"
    assert source["layers"]["status"] == "unknown"
    assert source["lifecycle"]["activation"] == "unknown"
    assert source["lifecycle"]["ingestion"] == "unknown"
    assert source["current_blocker"] == "activation_truth_unavailable"
