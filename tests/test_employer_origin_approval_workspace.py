from __future__ import annotations

from dataclasses import dataclass

from scripts.employer_origin_approval_workspace import (
    IMPLEMENTATION_APPROVAL_TOKEN,
    REGISTRATION_APPROVAL_TOKEN,
    evaluate_workspace_action,
    render_workspace_html,
    workspace_action_for_item,
)


@dataclass(frozen=True)
class CandidateSummary:
    candidate_id: int
    company_key: str
    company_name: str
    source_name_candidate: str
    source_family_candidate: str
    status: str
    risk_level: str
    latest_gate_order: int | None
    latest_gate_name: str | None
    blocked_gate_count: int
    manual_review_gate_count: int
    passed_gate_count: int
    total_gate_count: int


@dataclass(frozen=True)
class QueueItem:
    candidate: CandidateSummary
    next_action: str
    reason: str
    priority: int
    command: str | None


def candidate(company_key: str = "hdi") -> CandidateSummary:
    return CandidateSummary(
        candidate_id=1,
        company_key=company_key,
        company_name=company_key.upper(),
        source_name_candidate=f"{company_key}:hannover",
        source_family_candidate=company_key,
        status="connector_candidate",
        risk_level="low",
        latest_gate_order=None,
        latest_gate_name=None,
        blocked_gate_count=0,
        manual_review_gate_count=0,
        passed_gate_count=10,
        total_gate_count=10,
    )


def item(action: str) -> QueueItem:
    return QueueItem(
        candidate=candidate(),
        next_action=action,
        reason="test reason",
        priority=10,
        command="python -m scripts.run_employer_origin_agent_chain --company-key hdi",
    )


def test_connector_artifact_generation_requires_implementation_approval_token() -> None:
    plan = workspace_action_for_item(
        item("run_connector_artifact_generator"),
        target_location="hannover",
        reviewed_by="jens",
    )

    assert plan is not None
    assert plan.token_required == IMPLEMENTATION_APPROVAL_TOKEN
    assert "--write-connector" in plan.command
    assert "Bronze" in plan.allowed_boundary


def test_final_registration_approval_uses_existing_registration_token() -> None:
    plan = workspace_action_for_item(
        item("stop_explicit_approval_required"),
        target_location="hannover",
        reviewed_by="jens",
    )

    assert plan is not None
    assert plan.token_required == REGISTRATION_APPROVAL_TOKEN
    assert "--approval-token" in plan.command
    assert REGISTRATION_APPROVAL_TOKEN in plan.command


def test_workspace_action_is_blocked_when_write_actions_are_disabled() -> None:
    decision = evaluate_workspace_action(
        item("run_connector_artifact_generator"),
        requested_action="approve_connector_implementation",
        approval_token=IMPLEMENTATION_APPROVAL_TOKEN,
        write_actions_enabled=False,
        target_location="hannover",
        reviewed_by="jens",
    )

    assert not decision.allowed
    assert "--allow-write-actions" in decision.reason


def test_workspace_action_requires_exact_token() -> None:
    decision = evaluate_workspace_action(
        item("run_connector_artifact_generator"),
        requested_action="approve_connector_implementation",
        approval_token="approve",
        write_actions_enabled=True,
        target_location="hannover",
        reviewed_by="jens",
    )

    assert not decision.allowed
    assert IMPLEMENTATION_APPROVAL_TOKEN in decision.reason


def test_workspace_action_allows_current_bounded_action_with_exact_token() -> None:
    decision = evaluate_workspace_action(
        item("run_connector_artifact_generator"),
        requested_action="approve_connector_implementation",
        approval_token=IMPLEMENTATION_APPROVAL_TOKEN,
        write_actions_enabled=True,
        target_location="hannover",
        reviewed_by="jens",
    )

    assert decision.allowed
    assert decision.action_plan is not None
    assert "--write-connector" in decision.action_plan.command


def test_workspace_html_renders_read_only_dashboard_and_gate_summary() -> None:
    html = render_workspace_html(
        [item("run_connector_artifact_generator")],
        gates_by_candidate_id={},
        target_location="hannover",
        reviewed_by="jens",
        write_actions_enabled=False,
    )

    assert "Job-Pipeline Approval Workspace" in html
    assert "Sweet Spot — Balanced Intelligence" in html
    assert "Candidate Landscape" in html
    assert "read-only" in html
    assert "Approve connector implementation" in html
    assert "--allow-write-actions" in html


def test_workspace_html_uses_human_status_labels_and_progress() -> None:
    blocked_item = item("manual_review_stop")
    html = render_workspace_html(
        [blocked_item],
        gates_by_candidate_id={},
        target_location="hannover",
        reviewed_by="jens",
        write_actions_enabled=False,
    )

    assert "Review required" in html
    assert "manual_review_stop" in html
    assert "10 of 10 gates passed" in html
    assert "No bounded UI action available" not in html
    assert "This candidate is intentionally paused" in html
    assert "phase-tracker" in html
    assert "Gate progress" in html


def test_workspace_html_uses_05a_balanced_intelligence_language() -> None:
    html = render_workspace_html(
        [item("monitor_source_lifecycle")],
        gates_by_candidate_id={},
        target_location="hannover",
        reviewed_by="jens",
        write_actions_enabled=True,
    )

    assert "Job-Pipeline Approval Workspace" in html
    assert "Employer-Origin Agents · Sweet Spot — Balanced Intelligence" in html
    assert "Candidate Landscape" in html
    assert "Intelligence by design" in html
    assert "Active controlled" in html
