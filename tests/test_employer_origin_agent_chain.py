from __future__ import annotations

from scripts.run_employer_origin_agent_chain import (
    CONNECTOR_CANDIDATE_GATE,
    DETAIL_EVIDENCE_GATE,
    GateReview,
    child_command,
    connector_candidate_ready,
    needs_detail_evidence_repair,
    next_decision,
)


def gate(name: str, status: str, decision: str, stop_reason: str | None = None) -> GateReview:
    return GateReview(
        gate_name=name,
        gate_status=status,
        decision=decision,
        stop_reason=stop_reason,
    )


def test_needs_detail_evidence_repair_when_detail_gate_is_missing_or_not_passed() -> None:
    assert needs_detail_evidence_repair({})
    assert needs_detail_evidence_repair(
        {
            DETAIL_EVIDENCE_GATE: gate(
                DETAIL_EVIDENCE_GATE,
                "manual_review_required",
                "manual_review_required",
            )
        }
    )
    assert not needs_detail_evidence_repair(
        {
            DETAIL_EVIDENCE_GATE: gate(
                DETAIL_EVIDENCE_GATE,
                "passed",
                "continue",
            )
        }
    )


def test_connector_candidate_ready_requires_passed_build_connector_candidate() -> None:
    assert connector_candidate_ready(
        {
            CONNECTOR_CANDIDATE_GATE: gate(
                CONNECTOR_CANDIDATE_GATE,
                "passed",
                "build_connector_candidate",
            )
        }
    )
    assert not connector_candidate_ready(
        {
            CONNECTOR_CANDIDATE_GATE: gate(
                CONNECTOR_CANDIDATE_GATE,
                "passed",
                "continue",
            )
        }
    )


def test_next_decision_stops_without_repair_flag_when_detail_gate_is_blocked() -> None:
    decision = next_decision(
        {
            DETAIL_EVIDENCE_GATE: gate(
                DETAIL_EVIDENCE_GATE,
                "manual_review_required",
                "manual_review_required",
                "no concrete detail URLs",
            )
        },
        company_key="hdi",
        target_location="hannover",
        reviewed_by="jens",
        attempt_repair=False,
        write_connector=False,
    )

    assert decision.action == "stop_manual_review_required"
    assert decision.module is None
    assert "--attempt-repair" in decision.reason


def test_next_decision_runs_repair_when_enabled() -> None:
    decision = next_decision(
        {
            DETAIL_EVIDENCE_GATE: gate(
                DETAIL_EVIDENCE_GATE,
                "manual_review_required",
                "manual_review_required",
            )
        },
        company_key="hdi",
        target_location="hannover",
        reviewed_by="jens",
        attempt_repair=True,
        write_connector=False,
    )

    assert decision.action == "run_detail_evidence_repair"
    assert decision.module == "scripts.run_employer_origin_detail_evidence_repair_agent"
    assert "--company-key" in decision.args
    assert "hdi" in decision.args


def test_next_decision_runs_connector_candidate_after_detail_gate_passes() -> None:
    decision = next_decision(
        {
            DETAIL_EVIDENCE_GATE: gate(DETAIL_EVIDENCE_GATE, "passed", "continue"),
        },
        company_key="hdi",
        target_location="hannover",
        reviewed_by="jens",
        attempt_repair=True,
        write_connector=False,
    )

    assert decision.action == "run_connector_candidate_gate"
    assert decision.module == "scripts.run_employer_origin_connector_candidate_agent"


def test_next_decision_runs_connector_implementation_as_dry_run_by_default() -> None:
    decision = next_decision(
        {
            DETAIL_EVIDENCE_GATE: gate(DETAIL_EVIDENCE_GATE, "passed", "continue"),
            CONNECTOR_CANDIDATE_GATE: gate(
                CONNECTOR_CANDIDATE_GATE,
                "passed",
                "build_connector_candidate",
            ),
        },
        company_key="hdi",
        target_location="hannover",
        reviewed_by="jens",
        attempt_repair=True,
        write_connector=False,
    )

    assert decision.action == "run_connector_implementation_agent"
    assert decision.module == "scripts.run_employer_origin_connector_implementation_agent"
    assert "--dry-run" in decision.args


def test_child_command_uses_current_python_interpreter() -> None:
    command = child_command("scripts.example", ("--company-key", "hdi"))

    assert command[1:3] == ["-m", "scripts.example"]
    assert command[-2:] == ["--company-key", "hdi"]

def test_child_exit_interpretation_labels_exit_code_two_as_manual_review() -> None:
    from scripts.run_employer_origin_agent_chain import child_exit_interpretation_lines

    text = "\\n".join(child_exit_interpretation_lines(2))

    assert "child_step_completed: false" in text
    assert "child_gate_outcome: manual_review_required" in text
    assert "child_exit_code: 2" not in text

def test_active_controlled_source_completed_requires_lifecycle_and_no_open_review() -> None:
    from scripts.run_employer_origin_agent_chain import (
        GateReview,
        SourceCandidate,
        active_controlled_source_completed,
    )

    candidate = SourceCandidate(
        id=1,
        company_key="finanz_informatik",
        company_name="Finanz Informatik GmbH & Co. KG",
        source_name_candidate="finanz_informatik:hannover",
        status="active_controlled",
    )

    assert active_controlled_source_completed(
        candidate,
        {
            "source_lifecycle_tracking": GateReview(
                gate_name="source_lifecycle_tracking",
                gate_status="passed",
                decision="continue",
                stop_reason=None,
            ),
            "connector_candidate_gate": GateReview(
                gate_name="connector_candidate_gate",
                gate_status="passed",
                decision="build_connector_candidate",
                stop_reason=None,
            ),
        },
    )

    assert not active_controlled_source_completed(
        candidate,
        {
            "source_lifecycle_tracking": GateReview(
                gate_name="source_lifecycle_tracking",
                gate_status="passed",
                decision="continue",
                stop_reason=None,
            ),
            "detail_evidence_gate": GateReview(
                gate_name="detail_evidence_gate",
                gate_status="manual_review_required",
                decision="manual_review_required",
                stop_reason="still needs review",
            ),
        },
    )
