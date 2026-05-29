from __future__ import annotations

from scripts.run_employer_origin_connector_build_readiness_agent import (
    REQUIRED_PASSED_GATES,
    GateReview,
    SourceCandidate,
    evaluate_readiness,
)


def candidate(status: str = "manual_review_required") -> SourceCandidate:
    return SourceCandidate(
        id=2,
        company_key="hdi",
        company_name="HDI Group",
        candidate_url="https://careers.hdi.group/jobs",
        source_name_candidate="hdi:hannover",
        source_family_candidate="hdi",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status=status,
        risk_level="low",
    )


def gate(name: str, status: str = "passed", decision: str = "continue", evidence: dict | None = None) -> GateReview:
    return GateReview(
        gate_name=name,
        gate_status=status,
        decision=decision,
        stop_reason=None,
        evidence=evidence or {},
    )


def passed_gates() -> dict[str, GateReview]:
    gates = {name: gate(name) for name in REQUIRED_PASSED_GATES}
    gates["connector_candidate_gate"] = gate(
        "connector_candidate_gate",
        decision="build_connector_candidate",
        evidence={
            "connector_candidate_spec": {
                "detail_evidence": {
                    "detail_urls": ["https://careers.example.test/jobs/product-owner-data-platform"]
                }
            }
        },
    )
    return gates


def test_readiness_is_ready_when_required_gates_and_spec_are_present() -> None:
    outcome = evaluate_readiness(candidate(), passed_gates())

    assert outcome.status == "ready"
    assert outcome.decision == "connector_generation_allowed_before_final_approval"
    assert outcome.evidence["boundary"]["connector_registration_allowed"] is False
    assert outcome.evidence["boundary"]["bronze_persistence_allowed"] is False


def test_readiness_stops_when_candidate_is_active_controlled() -> None:
    outcome = evaluate_readiness(candidate(status="active_controlled"), passed_gates())

    assert outcome.status == "not_applicable"
    assert outcome.decision == "monitor_existing_source"


def test_readiness_stops_when_required_gate_is_manual_review() -> None:
    gates = passed_gates()
    gates["detail_evidence_gate"] = GateReview(
        gate_name="detail_evidence_gate",
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason="no concrete details",
        evidence={},
    )

    outcome = evaluate_readiness(candidate(), gates)

    assert outcome.status == "manual_review_required"
    assert outcome.decision == "stop_before_connector_generation"
    assert outcome.reason == "required gates are not all passed"


def test_readiness_stops_without_connector_candidate_spec() -> None:
    gates = passed_gates()
    gates["connector_candidate_gate"] = gate(
        "connector_candidate_gate",
        decision="build_connector_candidate",
        evidence={},
    )

    outcome = evaluate_readiness(candidate(), gates)

    assert outcome.status == "manual_review_required"
    assert outcome.reason == "connector_candidate_spec is missing"


def test_readiness_stops_when_spec_has_no_detail_urls() -> None:
    gates = passed_gates()
    gates["connector_candidate_gate"] = gate(
        "connector_candidate_gate",
        decision="build_connector_candidate",
        evidence={"connector_candidate_spec": {"detail_evidence": {"detail_urls": []}}},
    )

    outcome = evaluate_readiness(candidate(), gates)

    assert outcome.status == "manual_review_required"
    assert outcome.reason == "connector_candidate_spec has no concrete detail URLs"
