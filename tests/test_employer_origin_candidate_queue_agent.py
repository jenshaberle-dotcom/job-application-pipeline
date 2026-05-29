from __future__ import annotations

from scripts.run_employer_origin_agent_chain import GateReview
from scripts.run_employer_origin_candidate_queue_agent import (
    CONNECTOR_CANDIDATE_GATE,
    SOURCE_LIFECYCLE_GATE,
    CandidateSummary,
    build_queue,
    classify_queue_item,
    render_queue,
)


def candidate(
    company_key: str = "hdi",
    status: str = "candidate",
    candidate_id: int = 1,
) -> CandidateSummary:
    return CandidateSummary(
        candidate_id=candidate_id,
        company_key=company_key,
        company_name=company_key.upper(),
        source_name_candidate=f"{company_key}:hannover",
        status=status,
        risk_level="low",
        latest_gate_order=None,
        latest_gate_name=None,
        blocked_gate_count=0,
        manual_review_gate_count=0,
        passed_gate_count=0,
        total_gate_count=0,
    )


def gate(
    name: str,
    status: str,
    decision: str,
    stop_reason: str | None = None,
) -> GateReview:
    return GateReview(
        gate_name=name,
        gate_status=status,
        decision=decision,
        stop_reason=stop_reason,
    )


def test_active_controlled_candidate_prioritizes_missing_lifecycle_tracking() -> None:
    item = classify_queue_item(
        candidate("finanz_informatik", status="active_controlled"),
        {},
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=False,
    )

    assert item.next_action == "run_source_lifecycle_tracking"
    assert "run_employer_origin_source_lifecycle_tracking_agent" in (item.command or "")


def test_lifecycle_passed_active_candidate_is_monitor_only() -> None:
    item = classify_queue_item(
        candidate("finanz_informatik", status="active_controlled"),
        {
            SOURCE_LIFECYCLE_GATE: gate(SOURCE_LIFECYCLE_GATE, "passed", "continue"),
            CONNECTOR_CANDIDATE_GATE: gate(
                CONNECTOR_CANDIDATE_GATE,
                "passed",
                "build_connector_candidate",
            ),
            "detail_evidence_gate": gate("detail_evidence_gate", "passed", "continue"),
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=False,
    )

    assert item.next_action == "monitor_source_lifecycle"
    assert item.command is None


def test_blocked_detail_evidence_without_repair_is_manual_review_stop() -> None:
    item = classify_queue_item(
        candidate("hdi"),
        {
            "detail_evidence_gate": gate(
                "detail_evidence_gate",
                "manual_review_required",
                "manual_review_required",
                "no concrete detail URLs",
            )
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=False,
    )

    assert item.next_action == "stop_manual_review_required"
    assert item.command is None


def test_blocked_detail_evidence_with_repair_gets_chain_command() -> None:
    item = classify_queue_item(
        candidate("hdi"),
        {
            "detail_evidence_gate": gate(
                "detail_evidence_gate",
                "manual_review_required",
                "manual_review_required",
                "no concrete detail URLs",
            )
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    assert item.next_action == "run_detail_evidence_repair"
    assert "--attempt-repair" in (item.command or "")


def test_queue_sorting_prioritizes_lifecycle_then_implementation_then_repair() -> None:
    items = build_queue(
        [
            candidate("hdi", candidate_id=1),
            candidate("finanz_informatik", status="active_controlled", candidate_id=2),
            candidate("rossmann", candidate_id=3),
        ],
        {
            1: {
                "detail_evidence_gate": gate(
                    "detail_evidence_gate",
                    "manual_review_required",
                    "manual_review_required",
                )
            },
            2: {},
            3: {
                "detail_evidence_gate": gate("detail_evidence_gate", "passed", "continue"),
                CONNECTOR_CANDIDATE_GATE: gate(
                    CONNECTOR_CANDIDATE_GATE,
                    "passed",
                    "build_connector_candidate",
                ),
            },
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    assert [item.next_action for item in items] == [
        "run_source_lifecycle_tracking",
        "run_connector_implementation_agent",
        "run_detail_evidence_repair",
    ]


def test_render_queue_contains_actionable_command_when_available() -> None:
    item = classify_queue_item(
        candidate("hdi"),
        {
            "detail_evidence_gate": gate(
                "detail_evidence_gate",
                "manual_review_required",
                "manual_review_required",
            )
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    text = "\n".join(render_queue([item]))

    assert "Employer-Origin Candidate Queue" in text
    assert "next_action: run_detail_evidence_repair" in text
    assert "command: python -m scripts.run_employer_origin_agent_chain" in text

def test_completed_active_controlled_source_is_monitor_only_and_has_no_command() -> None:
    item = classify_queue_item(
        candidate("finanz_informatik", status="active_controlled"),
        {
            SOURCE_LIFECYCLE_GATE: gate(SOURCE_LIFECYCLE_GATE, "passed", "continue"),
            CONNECTOR_CANDIDATE_GATE: gate(
                CONNECTOR_CANDIDATE_GATE,
                "passed",
                "build_connector_candidate",
            ),
            "detail_evidence_gate": gate("detail_evidence_gate", "passed", "continue"),
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    assert item.next_action == "monitor_source_lifecycle"
    assert item.command is None
