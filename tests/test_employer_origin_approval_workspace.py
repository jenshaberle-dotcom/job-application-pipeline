from __future__ import annotations

from dataclasses import dataclass

from scripts.employer_origin_approval_workspace import (
    IMPLEMENTATION_APPROVAL_TOKEN,
    WorkspaceReassessmentItem,
    WorkspaceSearchStrategyRecommendation,
    REGISTRATION_APPROVAL_TOKEN,
    evaluate_workspace_action,
    filter_workspace_items,
    render_workspace_html,
    workspace_action_for_item,
    workspace_view_counts,
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

    assert "Employer-Origin Approval Workspace" in html
    assert "read-only" in html
    assert "Approve connector implementation" in html
    assert "--allow-write-actions" in html


def test_workspace_html_follows_balanced_intelligence_dashboard_language() -> None:
    html = render_workspace_html(
        [item("manual_review_stop")],
        gates_by_candidate_id={},
        target_location="hannover",
        reviewed_by="jens",
        write_actions_enabled=False,
    )

    assert "Sweet Spot — Balanced Intelligence" in html
    assert "Approval Control Surface" in html
    assert "Candidate Landscape" in html
    assert "Connector lifecycle phase" in html
    assert "StepStone remains a bounded discovery signal" in html


def test_workspace_filters_items_by_view_and_search_query() -> None:
    review_item = item("manual_review_stop")
    active_item = QueueItem(
        candidate=CandidateSummary(
            candidate_id=2,
            company_key="finanz_informatik",
            company_name="Finanz Informatik",
            source_name_candidate="finanz_informatik:hannover",
            source_family_candidate="finanz_informatik",
            status="active_controlled",
            risk_level="low",
            latest_gate_order=None,
            latest_gate_name=None,
            blocked_gate_count=0,
            manual_review_gate_count=0,
            passed_gate_count=14,
            total_gate_count=14,
        ),
        next_action="monitor_source_lifecycle",
        reason="active",
        priority=1,
        command=None,
    )

    counts = workspace_view_counts([review_item, active_item])
    assert counts["all"] == 2
    assert counts["review_required"] == 1
    assert counts["active"] == 1

    assert filter_workspace_items([review_item, active_item], selected_view="active") == [active_item]
    assert filter_workspace_items([review_item, active_item], search_query="finanz") == [active_item]


def test_workspace_html_renders_candidate_scaling_controls() -> None:
    html = render_workspace_html(
        [item("manual_review_stop")],
        gates_by_candidate_id={},
        target_location="hannover",
        reviewed_by="jens",
        write_actions_enabled=False,
        selected_view="review_required",
        search_query="hdi",
    )

    assert "Candidate status filters" in html
    assert "Review required" in html
    assert "Search candidates" in html
    assert "Showing 1 of 1 candidates" in html
    assert "Clear filters" in html


def test_render_workspace_shows_reassessment_queue_section() -> None:
    html = render_workspace_html(
        [item("manual_review_stop")],
        {},
        target_location="hannover",
        reviewed_by="jens",
        write_actions_enabled=False,
        selected_view="reassessment",
        reassessment_items=[
            WorkspaceReassessmentItem(
                queue_id=1,
                candidate_id=2,
                company_key="hdi",
                company_name="HDI Group",
                risk_level="high",
                priority=77,
                trigger_reason="unresolved employer-origin candidate still appears in market evidence",
                suggested_search_terms=("analytics",),
                status="open",
                updated_at="2026-05-31 07:01:21+00",
            )
        ],
    )

    assert "Reassessment Queue" in html
    assert "HDI Group" in html
    assert "terms: analytics" in html
    assert "Reassessment worklist mode" in html


def test_workspace_counts_reassessment_view_items() -> None:
    html = render_workspace_html(
        [item("manual_review_stop")],
        {},
        target_location="hannover",
        reviewed_by="jens",
        write_actions_enabled=False,
        reassessment_items=[
            WorkspaceReassessmentItem(
                queue_id=1,
                candidate_id=2,
                company_key="hdi",
                company_name="HDI Group",
                risk_level="high",
                priority=77,
                trigger_reason="reason",
                suggested_search_terms=("analytics",),
                status="open",
                updated_at=None,
            )
        ],
    )

    assert "Reassessment" in html
    assert "1</strong></a>" in html



def test_workspace_html_renders_learning_loop_section() -> None:
    from scripts.employer_origin_approval_workspace import WorkspaceSearchTermConfidence

    html = render_workspace_html(
        [item('manual_review_stop')],
        gates_by_candidate_id={},
        target_location='hannover',
        reviewed_by='jens',
        write_actions_enabled=False,
        selected_view='learning',
        confidence_items=[
            WorkspaceSearchTermConfidence(
                suggested_term='analytics',
                source_family_candidate='hdi',
                sample_size=4,
                success_count=3,
                failure_count=1,
                noise_count=0,
                confidence_score='75.00',
                confidence_level='high',
                created_at='2026-05-31',
            )
        ],
    )

    assert 'Learning Loop' in html
    assert 'analytics' in html
    assert 'confidence: 75.00%' in html
    assert 'Learning loop mode' in html



def test_workspace_html_renders_strategy_recommendations() -> None:
    html = render_workspace_html(
        [item("manual_review_stop")],
        gates_by_candidate_id={},
        target_location="hannover",
        reviewed_by="jens",
        write_actions_enabled=False,
        selected_view="strategy",
        strategy_recommendations=[
            WorkspaceSearchStrategyRecommendation(
                recommendation_id=1,
                company_key="hdi",
                source_family_candidate="hdi",
                suggested_term="analytics",
                recommendation_type="ADD_TRIAL_TERM",
                recommendation_status="pending_review",
                autonomy_level="manual_approval_required",
                confidence_score="100.00",
                confidence_level="low",
                sample_size=1,
                false_negative_risk_level="high",
                false_negative_sighting_count=2,
                guardrail_decision="bounded_trial_recommended",
                reason="High false-negative risk with validation evidence.",
                updated_at="2026-05-31 12:00:00+00",
            )
        ],
    )

    assert "Strategy Recommendations" in html
    assert "analytics" in html
    assert "Add trial term" in html
    assert "Search profiles are not changed automatically" in html
