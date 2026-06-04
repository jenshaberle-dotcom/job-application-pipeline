from __future__ import annotations

from scripts.run_employer_origin_connector_candidate_agent import (
    SourceCandidate,
    build_connector_candidate_spec,
    connector_candidate_outcome,
    missing_or_unpassed_preconditions,
    pascal_case,
    snake_case,
)


def make_candidate(source_type: str = "employer_origin_career_site") -> SourceCandidate:
    return SourceCandidate(
        id=2,
        company_key="hdi",
        company_name="HDI Group",
        candidate_url="https://careers.hdi.group/jobs",
        source_name_candidate="hdi:hannover",
        source_family_candidate="hdi",
        source_target_candidate="hannover",
        source_type_candidate=source_type,
        status="connector_candidate",
        risk_level="low",
    )


def make_passed_gate(gate_name: str, evidence: dict | None = None) -> dict:
    return {
        "gate_name": gate_name,
        "gate_order": 1,
        "is_hard_gate": True,
        "gate_status": "passed",
        "decision": "continue",
        "stop_reason": None,
        "evidence": evidence or {},
    }


def make_passed_gate_set() -> dict[str, dict]:
    gates = {
        name: make_passed_gate(name)
        for name in (
            "company_candidate",
            "source_discovery",
            "risk_gate",
            "technical_reachability_gate",
            "scope_gate",
            "defensive_preview_gate",
            "relevance_gate",
            "detail_evidence_gate",
            "incremental_uniqueness_gate",
        )
    }
    gates["detail_evidence_gate"]["evidence"] = {
        "details": [
            {
                "url": "https://careers.hdi.group/jobs/product-owner",
                "title": "Product Owner",
            }
        ]
    }
    gates["incremental_uniqueness_gate"]["evidence"] = {
        "detail_candidates_considered": 1,
        "existing_evidence_rows_considered": 399,
        "uniqueness_counts": {"incrementally_unique_candidate": 1},
        "results": [
            {
                "candidate_url": "https://careers.hdi.group/jobs/product-owner",
                "uniqueness_decision": "incrementally_unique_candidate",
            }
        ],
    }
    return gates


def test_name_helpers_create_python_names() -> None:
    assert snake_case("Finanz Informatik") == "finanz_informatik"
    assert pascal_case("finanz_informatik") == "FinanzInformatik"


def test_missing_preconditions_are_reported() -> None:
    gates = make_passed_gate_set()
    gates["detail_evidence_gate"]["gate_status"] = "manual_review_required"

    missing = missing_or_unpassed_preconditions(gates)

    assert missing == [
        {
            "gate_name": "detail_evidence_gate",
            "problem": "gate_not_passed",
            "gate_status": "manual_review_required",
            "decision": "continue",
            "stop_reason": None,
        }
    ]


def test_connector_candidate_outcome_requires_passed_preconditions() -> None:
    gates = make_passed_gate_set()
    del gates["incremental_uniqueness_gate"]

    outcome = connector_candidate_outcome(make_candidate(), gates)

    assert outcome.gate_status == "manual_review_required"
    assert outcome.decision == "manual_review_required"
    assert outcome.stop_reason == "precondition gates are not all passed"


def test_connector_candidate_outcome_blocks_non_employer_origin_type() -> None:
    outcome = connector_candidate_outcome(
        make_candidate(source_type="aggregator"),
        make_passed_gate_set(),
    )

    assert outcome.gate_status == "failed"
    assert outcome.decision == "abort_documented"


def test_connector_candidate_outcome_passes_with_connector_spec() -> None:
    outcome = connector_candidate_outcome(make_candidate(), make_passed_gate_set())

    assert outcome.gate_name == "connector_candidate_gate"
    assert outcome.gate_status == "passed"
    assert outcome.decision == "passed"

    spec = outcome.evidence["connector_candidate_spec"]
    assert spec["recommended_connector"]["module_path"] == "src/connectors/hdi.py"
    assert spec["recommended_connector"]["class_name"] == "HdiConnector"
    assert spec["bounded_implementation_contract"]["bronze_persistence_approved_by_this_gate"] is False
    assert spec["bounded_implementation_contract"]["generated_exports_are_process_inputs"] is False


def test_build_connector_candidate_spec_carries_detail_and_uniqueness_evidence() -> None:
    spec = build_connector_candidate_spec(make_candidate(), make_passed_gate_set())

    assert spec["detail_evidence"]["detail_urls"] == ["https://careers.hdi.group/jobs/product-owner"]
    assert spec["incremental_uniqueness"]["uniqueness_counts"] == {"incrementally_unique_candidate": 1}
    assert "connector would need CSV/Excel/generated export artifacts as inputs" in spec["stop_conditions_for_implementation"]

def test_concrete_job_detail_url_accepts_specific_job_pages_and_rejects_overviews() -> None:
    from scripts.run_employer_origin_connector_candidate_agent import concrete_job_detail_url

    assert concrete_job_detail_url(
        "https://www.f-i.de/de/karriere/offene-stellen/hannover/product-owner-osplus-versiegelung-m-w-d"
    )
    assert concrete_job_detail_url("https://careers.example.test/jobs/product-owner-data-platform")

    assert not concrete_job_detail_url("https://careers.hdi.group/de/karriere/jobs")
    assert not concrete_job_detail_url("https://careers.hdi.group/en/your_career_opportunities")
    assert not concrete_job_detail_url("https://careers.hdi.group/en/privacy")


def test_connector_candidate_outcome_requires_concrete_job_detail_urls() -> None:
    gates = make_passed_gate_set()
    gates["detail_evidence_gate"]["evidence"] = {
        "details": [
            {"url": "https://careers.hdi.group/de/karriere/jobs"},
            {"url": "https://careers.hdi.group/en/your_career_opportunities"},
            {"url": "https://careers.hdi.group/en/privacy"},
        ]
    }

    outcome = connector_candidate_outcome(make_candidate(), gates)

    assert outcome.gate_status == "manual_review_required"
    assert outcome.decision == "manual_review_required"
    assert outcome.stop_reason == "detail evidence does not contain concrete job-detail URLs"
    assert "https://careers.hdi.group/en/privacy" in outcome.evidence["rejected_detail_urls"]
