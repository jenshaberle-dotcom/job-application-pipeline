from src.connectors.registry import build_default_connector_registry
from src.search_intelligence.source_connector_overview import build_source_connector_overview


def _source(payload: dict[str, object], source_name: str) -> dict[str, object]:
    sources = payload["sources"]
    assert isinstance(sources, list)
    return next(item for item in sources if item["source_name"] == source_name)


def test_active_generic_source_projects_proof_pass_and_retires_old_final_gate() -> None:
    source_name = "generic_origin:example"
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
    )

    source = _source(payload, source_name)
    admission = source["gates"]["source_admission_gate"]
    assert admission == source["gates"]["connector_validation_gate"]
    assert admission["status"] == "passed"
    assert admission["decision"] == "proof_pass_source_admission"
    assert admission["passed"] is True
    assert admission["truth_source"] == "generic_origin_activation_projection"
    assert source["gates"]["final_approval_gate"] == {
        "status": "not_applicable",
        "decision": None,
        "passed": True,
        "required": False,
        "truth_source": "retired_by_generic_evidence_driven_layer_model",
    }
    assert source["lifecycle"]["validation"] == "passed"
    assert source["lifecycle"]["final_approval"] == "not_applicable"


def test_generic_source_without_materialized_proof_is_not_optimistically_valid() -> None:
    source_name = "generic_origin:example"
    payload = build_source_connector_overview(
        registry=build_default_connector_registry(),
        candidates=[
            {
                "candidate_id": 17,
                "source_name": source_name,
                "company_name": "Example GmbH",
                "candidate_status": "candidate",
                "connector_validation_gate_status": "passed",
                "final_approval_gate_status": "passed",
                "final_approval_gate_decision": "approve_connector_registration",
            }
        ],
    )

    source = _source(payload, source_name)
    admission = source["gates"]["source_admission_gate"]
    assert admission["status"] == "not_materialized"
    assert admission["passed"] is False
    assert source["gates"]["final_approval_gate"]["required"] is False
    assert source["current_blocker"] == "generic_proof_not_materialized"


def test_generic_zero_bronze_is_observation_state_not_source_invalidity() -> None:
    source_name = "generic_origin:example"
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
                "total_loaded": 0,
                "inserted_count": 0,
            }
        ],
    )

    source = _source(payload, source_name)
    assert source["gates"]["source_admission_gate"]["passed"] is True
    assert source["activation"]["active"] is True
    assert source["activation"]["status"] == "active_last_run_0_jobs"
    assert source["current_blocker"] is None
    assert source["next_action"] == (
        "Active Employer-Origin source; latest ingestion loaded 0 jobs and inserted 0. "
        "Activation alone is not evidence of current Product delivery"
    )


def test_active_generic_latest_failed_run_remains_attention_worthy() -> None:
    source_name = "generic_origin:example"
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
                "last_ingestion_status": "failed",
                "total_loaded": 0,
                "inserted_count": 0,
            }
        ],
    )

    source = _source(payload, source_name)
    assert source["activation"]["active"] is True
    assert source["current_blocker"] == "employer_origin_latest_run_failed"
    assert source["next_action"] == "Resolve the latest Employer-Origin ingestion failure"
