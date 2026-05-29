from __future__ import annotations

from scripts.run_employer_origin_final_approval_gate_agent import (
    APPROVAL_TOKEN,
    GateReview,
    SourceCandidate,
    evaluate_final_approval,
)


def candidate() -> SourceCandidate:
    return SourceCandidate(
        id=1,
        company_key="example",
        source_name_candidate="example:hannover",
        status="connector_candidate",
    )


def gate(status: str = "passed", decision: str = "ready_for_final_approval") -> GateReview:
    return GateReview(
        gate_name="connector_validation_gate",
        gate_status=status,
        decision=decision,
        stop_reason=None,
    )


def test_final_approval_requires_validation_gate() -> None:
    outcome = evaluate_final_approval(
        candidate=candidate(),
        gates={},
        approval_token=APPROVAL_TOKEN,
        approved_by="jens",
    )

    assert outcome.gate_status == "manual_review_required"
    assert outcome.decision == "approval_blocked"


def test_final_approval_requires_exact_token() -> None:
    outcome = evaluate_final_approval(
        candidate=candidate(),
        gates={"connector_validation_gate": gate()},
        approval_token="yes",
        approved_by="jens",
    )

    assert outcome.gate_status == "manual_review_required"
    assert outcome.decision == "approval_token_required"


def test_final_approval_passes_with_validation_and_token() -> None:
    outcome = evaluate_final_approval(
        candidate=candidate(),
        gates={"connector_validation_gate": gate()},
        approval_token=APPROVAL_TOKEN,
        approved_by="jens",
    )

    assert outcome.gate_status == "passed"
    assert outcome.decision == "approve_connector_registration"
    assert outcome.evidence["boundary"]["bronze_persistence_allowed"] is False

def test_final_approval_is_not_applicable_for_active_controlled_source() -> None:
    active = SourceCandidate(
        id=1,
        company_key="finanz_informatik",
        source_name_candidate="finanz_informatik:hannover",
        status="active_controlled",
    )

    outcome = evaluate_final_approval(
        candidate=active,
        gates={"connector_validation_gate": gate()},
        approval_token=APPROVAL_TOKEN,
        approved_by="jens",
    )

    assert outcome.gate_status == "not_applicable"
    assert outcome.decision == "monitor_existing_source"
    assert outcome.stop_reason == "candidate is already active_controlled"
