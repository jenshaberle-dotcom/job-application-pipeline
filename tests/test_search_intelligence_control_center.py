from __future__ import annotations
from dataclasses import replace

from scripts.search_intelligence_control_center import (
    AgentGateReview,
    ControlCenterActionRun,
    BUILD_APPROVAL_TOKEN,
    EVIDENCE_REPAIR_TOKEN,
    NEXT_SAFE_ACTION_TOKEN,
    REGISTRATION_APPROVAL_TOKEN,
    ControlCenterCandidate,
    OrchestratorAttentionStep,
    build_approval_command,
    evidence_repair_command,
    next_safe_action_command,
    registration_approval_command,
    render_control_center,
)


def candidate(**overrides: object) -> ControlCenterCandidate:
    data = dict(
        candidate_id=2,
        company_key="hdi",
        company_name="HDI Group",
        candidate_url="https://careers.hdi.group/en/your_career_opportunities/job_board",
        source_name_candidate="hdi:hannover",
        source_type_candidate="employer_origin_career_site",
        status="manual_review_required",
        operational_risk_level="low",
        false_negative_risk_level="critical",
        reassessment_status="open",
        reassessment_reason="unresolved employer-origin candidate has five or more recent aggregator sightings",
        generation_status="gate_reassessment_required",
        generation_recommendation="rerun_employer_origin_gate_reassessment",
        build_status="build_approval_required",
        build_recommendation="request_explicit_build_approval",
        build_mode="bounded_investigation_connector",
        build_next_command="python -m scripts.run_approval_gated_connector_build_agent --company-key hdi --reviewed-by jens --approve-build --write",
        connector_module_path="src/connectors/hdi.py",
        connector_test_path="tests/test_hdi_connector.py",
        connector_docs_path="docs/planning/active/source-candidates/hdi_connector_candidate.md",
        gate_passed_count=8,
        gate_manual_review_count=2,
        gate_blocked_count=0,
        gate_total_count=16,
        latest_blocking_gate="detail_evidence_gate",
        latest_blocking_reason="bounded repair found no concrete detail pages with profile and target/remote signals",
        connector_validation_status=None,
        connector_validation_decision=None,
        final_approval_status=None,
        final_approval_decision=None,
    )
    data.update(overrides)
    return ControlCenterCandidate(**data)


def candidates() -> list[ControlCenterCandidate]:
    return [
        candidate(),
        candidate(
            candidate_id=1,
            company_key="finanz_informatik",
            company_name="Finanz Informatik GmbH & Co. KG",
            source_name_candidate="finanz_informatik:hannover",
            status="active_controlled",
            false_negative_risk_level=None,
            reassessment_status=None,
            build_status=None,
            build_recommendation=None,
            latest_blocking_gate=None,
            latest_blocking_reason=None,
            gate_passed_count=14,
            gate_manual_review_count=0,
            gate_total_count=16,
        ),
    ]


def gate_review(
    *,
    gate_name: str,
    decision: str,
    company_name: str = "enercity AG",
    company_key: str = "enercity",
    candidate_id: int = 4,
) -> AgentGateReview:
    return AgentGateReview(
        candidate_id=candidate_id,
        company_key=company_key,
        company_name=company_name,
        source_name_candidate=f"{company_key}:discovery",
        gate_name=gate_name,
        gate_status="passed",
        decision=decision,
        stop_reason=None,
        reviewed_by="jens",
        created_at=None,
    )


def action_run(**overrides: object) -> ControlCenterActionRun:
    data = dict(
        action_run_id=17,
        action_type="rerun_evidence_repair",
        company_key="hdi",
        candidate_id=2,
        reviewed_by="jens",
        triggered_from="control_center",
        status="failed",
        exit_code=1,
        started_at="2026-06-04 01:23:00+00",
        finished_at="2026-06-04 01:23:05+00",
        error_summary="command failed before gate review persistence",
        stdout_tail="",
        stderr_tail="Traceback summary",
        gate_review_created=False,
        gate_review_gate_name="detail_evidence_gate",
        gate_review_status=None,
        gate_review_decision=None,
        gate_review_created_at=None,
    )
    data.update(overrides)
    return ControlCenterActionRun(**data)


def test_control_center_renders_real_sidebar_tabs_and_dashboard_only_by_default() -> None:
    html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=False,
    )

    assert "Search Intelligence" in html
    assert "class=\"side-tabs nav\"" in html
    assert "<nav class='top-nav'" not in html
    assert 'href="/?tab=dashboard"' in html
    assert 'href="/?tab=health"' in html
    assert 'href="/?tab=review-queue"' in html
    assert 'href="/?tab=connectors"' not in html
    assert 'href="/?tab=approvals"' not in html
    assert 'href="/?tab=orchestrator"' in html
    assert 'href="/?tab=agent-monitor"' in html
    assert 'href="/?tab=gaps"' in html
    assert 'href="/?tab=jobs"' in html
    assert 'href="/?tab=demo-chain"' in html
    assert "Search Intelligence Overview" in html
    assert "Dataflow Live" in html
    assert "Controlled evidence threads" in html
    assert "Source Landscape & Risk Overview" in html
    assert "Controlled Intelligence Loop" in html
    assert "System health and diagnostics" not in html
    assert "Stop UI" in html
    assert "/actions/shutdown" in html


def test_control_center_renders_health_as_separate_page_not_anchor_scroll() -> None:
    html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=False,
        active_tab="health",
    )

    assert "System health and diagnostics" in html
    assert "Connector and candidate diagnostics" in html
    assert "Operational view for controlled sources" in html
    assert '<section class="legacy-shell">' not in html
    assert "Search Intelligence Overview" not in html
    assert "Candidate backlog" not in html


def test_control_center_renders_review_queue_for_human_decisions() -> None:
    html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=False,
        active_tab="review-queue",
    )

    assert "Human decision workspace" in html
    assert "Evidence review required" in html
    assert "Approval required" in html
    assert "Active / monitor only" in html
    assert "HDI Group" in html
    assert BUILD_APPROVAL_TOKEN in html
    assert "Review evidence repair action" in html
    assert "<dialog" in html
    assert "This action will not" in html
    assert "Prepared for S8A5 approval-safe actions" not in html
    assert '<section class="legacy-shell">' not in html
    assert "Search Intelligence Overview" not in html
    assert "Candidate backlog" not in html


def test_review_queue_renders_last_action_run_diagnostics() -> None:
    html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=True,
        active_tab="review-queue",
        action_runs=[action_run()],
    )

    assert "Last action run" in html
    assert "Rerun evidence repair" in html
    assert "Failed" in html
    assert "command failed before gate review persistence" in html
    assert "The command failed before the expected gate result was persisted." in html
    assert "Show technical diagnostics" in html
    assert "Traceback summary" in html
    assert "Gate review" in html
    assert "not written" in html




def test_review_queue_renders_human_readable_next_safe_action_failure() -> None:
    early_candidate = candidate(
        company_key="adesso",
        company_name="adesso SE",
        source_name_candidate="adesso:discovery",
        gate_passed_count=0,
        gate_total_count=16,
        build_status=None,
        build_recommendation=None,
        latest_blocking_gate="detail_evidence_gate",
        latest_blocking_reason="early gates still missing",
    )
    html = render_control_center(
        [early_candidate],
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=True,
        active_tab="review-queue",
        action_runs=[
            action_run(
                action_type="run_next_safe_action",
                company_key="adesso",
                candidate_id=2,
                error_summary="Next safe action failed before completion. Last diagnostic: child_command_failed: action=run_initial_gate_review exit_code=1 module=scripts.run_employer_origin_gate_agent",
                stdout_tail="candidate_id: 6\nnext_safe_action: run_initial_gate_review",
                stderr_tail="child_command_failed: action=run_initial_gate_review exit_code=1 module=scripts.run_employer_origin_gate_agent",
            )
        ],
    )

    assert "Run next safe action · Failed" in html
    assert "Next safe action failed before completion." in html
    assert "child_command_failed: action=run_initial_gate_review" in html
    assert "Show technical diagnostics" in html

def test_control_center_renders_orchestrator_attention_tab() -> None:
    html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=False,
        active_tab="orchestrator",
        orchestrator_steps=[
            OrchestratorAttentionStep(
                run_id=7,
                step_order=3,
                step_name="approval_queue_review",
                step_status="attention_required",
                action_mode="manual_approval_required",
                recommendation="Review explicit connector build approvals.",
                reason="Approval queue is not empty.",
            )
        ],
    )

    assert "Nightly Intelligence Cycle Attention" in html
    assert "Review explicit connector build approvals." in html
    assert "python -m scripts.run_nightly_search_intelligence_orchestrator --reviewed-by jens --write" in html
    assert "Latest persisted orchestrator steps" in html
    assert '<section class="legacy-shell">' not in html
    assert "Search Intelligence Overview" not in html


def test_control_center_renders_registration_approval_after_validation() -> None:
    html = render_control_center(
        [
            candidate(
                build_status="artifacts_present",
                build_recommendation="run_connector_validation",
                connector_validation_status="passed",
                connector_validation_decision="ready_for_final_approval",
                final_approval_status="manual_review_required",
                final_approval_decision="manual_review_required",
            )
        ],
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=True,
        active_tab="review-queue",
    )

    assert "Registration approval" in html
    assert REGISTRATION_APPROVAL_TOKEN in html
    assert "approve-registration" in html


def test_build_approval_command_is_bounded_to_s6c_build_only() -> None:
    command = build_approval_command("hdi", "jens")

    assert command == (
        "python",
        "-m",
        "scripts.run_approval_gated_connector_build_agent",
        "--company-key",
        "hdi",
        "--reviewed-by",
        "jens",
        "--approve-build",
        "--write",
    )


def test_registration_approval_command_uses_existing_final_gate_token() -> None:
    command = registration_approval_command("hdi", "hannover", "jens")

    assert "scripts.run_employer_origin_agent_chain" in command
    assert "--approval-token" in command
    assert REGISTRATION_APPROVAL_TOKEN in command



def test_control_center_uses_full_jinja_shell_and_svg_first_dashboard() -> None:
    html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=False,
    )

    assert "<style>" in html
    assert "<svg viewBox=\"0 0 980 390\"" in html
    assert "SVG scalable" in html
    assert "Responsive SVG-first visuals" in html
    assert "Jinja2 boundary" in html
    assert "No Bronze write" in html
    assert "No scheduler change" in html


def test_control_center_dashboard_shows_success_and_blocked_paths() -> None:
    html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=False,
    )

    assert "Finanz Informatik GmbH &amp; Co. KG" in html
    assert "Active controlled" in html
    assert "HDI Group" in html
    assert "Detail evidence gate" in html
    assert "Repair evidence" in html



def test_control_center_renders_agent_monitor_with_real_lifecycle_signals() -> None:
    html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=False,
        active_tab="agent-monitor",
    )

    assert "Agent Health Monitor" in html
    assert "Candidate Lifecycle Agent" in html
    assert "Detail Evidence Repair Agent" in html
    assert "Connector Artifact Generation Agent" in html
    assert "Nightly Intelligence Orchestrator" in html
    assert "HDI Group" in html
    assert "bounded repair found no concrete detail pages with profile and target/remote signals" in html
    assert "No source activation or Bronze persistence" in html
    assert "Search Intelligence Overview" not in html


def test_control_center_agent_monitor_marks_missing_signals_explicitly_without_gate_history() -> None:
    html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=False,
        active_tab="agent-monitor",
    )

    assert "No current validation signal" in html
    assert "No persisted validation result in current view" in html
    assert "not faked, explicitly marked" in html



def test_control_center_agent_monitor_uses_gate_review_history() -> None:
    html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=False,
        active_tab="agent-monitor",
        gate_reviews=[
            gate_review(
                gate_name="connector_validation_gate",
                decision="ready_for_final_approval",
            ),
            gate_review(
                gate_name="final_approval_gate",
                decision="approve_connector_registration",
            ),
        ],
    )

    assert "Connector Validation Agent" in html
    assert "Final Approval Gate Agent" in html
    assert "Passed historical signal" in html
    assert "1 persisted gate-review signal(s)" in html
    assert "Gate reviews: enercity AG" in html
    assert "No current validation signal" not in html
    assert "No current final approval signal" not in html



def test_control_center_renders_product_quality_candidate_gap_jobs_and_demo_tabs() -> None:
    candidate_html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=False,
        active_tab="connectors",
    )
    assert "Human decision workspace" in candidate_html
    assert "Evidence review required" in candidate_html
    assert "Active / monitor only" in candidate_html
    assert '<section class="legacy-shell">' not in candidate_html

    gaps_html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=False,
        active_tab="gaps",
    )
    assert "Market demand and capability gaps" in gaps_html
    assert "Gold model needed" in gaps_html
    assert "intentionally avoids fake analytics" in gaps_html
    assert '<section class="legacy-shell">' not in gaps_html

    jobs_html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=False,
        active_tab="jobs",
    )
    assert "New jobs and application drafts" in jobs_html
    assert "Application safety boundary" in jobs_html
    assert '<section class="legacy-shell">' not in jobs_html

    demo_html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=False,
        active_tab="demo-chain",
    )
    assert "Discovered company → approved connector" in demo_html
    assert "not blind crawling" in demo_html
    assert "No auto-PR" in demo_html
    assert '<section class="legacy-shell">' not in demo_html



def test_control_center_routes_legacy_candidate_and_approval_tabs_to_review_queue() -> None:
    for old_tab in ("connectors", "approvals"):
        html = render_control_center(
            candidates(),
            reviewed_by="jens",
            target_location="hannover",
            write_actions_enabled=False,
            active_tab=old_tab,
        )

        assert "Human decision workspace" in html
        assert "Review Queue" in html
        assert '<section class="legacy-shell">' not in html



def test_evidence_repair_command_is_bounded_to_agent_chain_repair() -> None:
    command = evidence_repair_command("hdi", "hannover", "jens")

    assert command == (
        "python",
        "-m",
        "scripts.run_employer_origin_agent_chain",
        "--company-key",
        "hdi",
        "--target-location",
        "hannover",
        "--reviewed-by",
        "jens",
        "--attempt-repair",
    )


def test_review_queue_renders_evidence_repair_action_disabled_by_default() -> None:
    html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=False,
        active_tab="review-queue",
    )

    assert "/actions/rerun-evidence-repair" in html
    assert EVIDENCE_REPAIR_TOKEN in html
    assert "Rerun bounded evidence repair" in html
    assert "Start the UI with" in html
    assert "data-dialog-target" in html
    assert "disabled" in html
    assert 'placeholder="run_evidence_repair"' not in html


def test_review_queue_enables_evidence_repair_action_in_write_mode() -> None:
    html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=True,
        active_tab="review-queue",
    )

    assert "/actions/rerun-evidence-repair" in html
    assert EVIDENCE_REPAIR_TOKEN in html
    assert "Rerun bounded evidence repair" in html
    assert "Start the UI with <code>--allow-write-actions</code>" not in html
    assert "data-dialog-target" in html
    assert 'placeholder="run_evidence_repair"' not in html



def test_review_queue_uses_dialog_actions_without_visible_token_inputs() -> None:
    html = render_control_center(
        candidates(),
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=True,
        active_tab="review-queue",
    )

    assert "<dialog" in html
    assert "Review evidence repair action" in html
    assert 'type="hidden" name="approval_token" value="run_evidence_repair"' in html
    assert 'placeholder="run_evidence_repair"' not in html
    assert "This action will not" in html
    assert "Run bounded evidence repair" in html



def test_review_queue_renders_next_safe_action_for_early_gate_candidates() -> None:
    early_candidate = candidate(
        company_key="adesso",
        company_name="adesso SE",
        source_name_candidate="adesso:discovery",
        gate_passed_count=0,
        gate_total_count=16,
        build_status=None,
        build_recommendation=None,
        latest_blocking_gate="detail_evidence_gate",
        latest_blocking_reason="detail evidence repair is premature while early gates are still missing",
    )
    html = render_control_center(
        [early_candidate],
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=True,
        active_tab="review-queue",
    )

    assert "/actions/run-next-safe-action" in html
    assert "Run initial gate review" in html
    assert 'type="hidden" name="approval_token" value="run_next_safe_action"' in html
    assert "not detail-evidence repair" in html
    assert "/actions/rerun-evidence-repair" not in html


def test_next_safe_action_command_delegates_to_orchestrator_script() -> None:
    command = next_safe_action_command("adesso", "hannover", "jens")

    assert command == (
        "python",
        "-m",
        "retired_next_action_agent_removed_consistency001b",
        "--company-key",
        "adesso",
        "--target-location",
        "hannover",
        "--reviewed-by",
        "jens",
    )



def test_review_queue_renders_connector_validation_action_for_connector_candidates() -> None:
    base_candidates = candidates()
    connector_candidates = [
        replace(
            base_candidates[0],
            status="connector_candidate",
            gate_passed_count=10,
            gate_total_count=16,
            latest_blocking_gate=None,
            latest_blocking_reason=None,
        ),
        *base_candidates[1:],
    ]

    html = render_control_center(
        connector_candidates,
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=True,
        active_tab="review-queue",
    )

    assert "/actions/run-connector-validation" in html
    assert "Run connector validation" in html
    assert 'type="hidden" name="approval_token" value="run_connector_validation"' in html
    assert "The next safe step is connector validation" in html


def test_review_queue_stops_terminal_early_gate_for_disallowed_auth_url() -> None:
    blocked_candidate = candidate(
        company_key="locked_source",
        company_name="Locked Source GmbH",
        candidate_url="https://example.com/login/jobs",
        source_name_candidate="locked_source:discovery",
        status="abort_documented",
        gate_passed_count=1,
        gate_total_count=16,
        build_status=None,
        build_recommendation=None,
        latest_blocking_gate="source_discovery",
        latest_blocking_status="failed",
        latest_blocking_decision="abort_documented",
        latest_blocking_reason="candidate URL appears to require authentication",
    )
    html = render_control_center(
        [blocked_candidate],
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=True,
        active_tab="review-queue",
    )

    assert "No safe automated action" in html
    assert "candidate URL appears to require authentication" in html
    assert "will not rerun the same automated step" in html
    assert "/actions/run-next-safe-action" not in html
    assert "Run initial gate review" not in html



def test_review_queue_stops_terminal_early_gate_when_only_candidate_status_is_terminal() -> None:
    blocked_candidate = candidate(
        company_key="adesso",
        company_name="adesso SE",
        source_name_candidate="adesso:discovery",
        status="abort_documented",
        gate_passed_count=1,
        gate_total_count=16,
        build_status=None,
        build_recommendation=None,
        latest_blocking_gate="source_discovery",
        latest_blocking_status=None,
        latest_blocking_decision=None,
        latest_blocking_reason="candidate URL appears to require authentication",
    )
    html = render_control_center(
        [blocked_candidate],
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=True,
        active_tab="review-queue",
    )

    assert "No safe automated action" in html
    assert "candidate URL appears to require authentication" in html
    assert "/actions/run-next-safe-action" not in html
    assert "Run initial gate review" not in html

def test_review_queue_still_runs_initial_gate_when_only_premature_detail_repair_blocked() -> None:
    early_candidate = candidate(
        company_key="adesso",
        company_name="adesso SE",
        source_name_candidate="adesso:discovery",
        gate_passed_count=0,
        gate_total_count=16,
        build_status=None,
        build_recommendation=None,
        latest_blocking_gate="detail_evidence_gate",
        latest_blocking_status="manual_review_required",
        latest_blocking_decision="manual_review_required",
        latest_blocking_reason="detail evidence repair is premature while early gates are still missing",
    )
    html = render_control_center(
        [early_candidate],
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=True,
        active_tab="review-queue",
    )

    assert "Run initial gate review" in html
    assert "/actions/run-next-safe-action" in html
    assert "not detail-evidence repair" in html


def test_review_queue_stops_terminal_detail_gate_after_early_gates_passed() -> None:
    blocked_candidate = candidate(
        company_key="hdi",
        company_name="HDI Group",
        source_name_candidate="hdi:hannover",
        gate_passed_count=7,
        gate_total_count=16,
        build_status=None,
        build_recommendation=None,
        latest_blocking_gate="detail_evidence_gate",
        latest_blocking_status="manual_review_required",
        latest_blocking_decision="manual_review_required",
        latest_blocking_reason="bounded repair found no concrete detail pages",
    )
    html = render_control_center(
        [blocked_candidate],
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=True,
        active_tab="review-queue",
    )

    assert "Human review required" in html
    assert "bounded repair found no concrete detail pages" in html
    assert "/actions/rerun-evidence-repair" not in html


def test_next_safe_action_recovers_source_discovery_auth_false_positive() -> None:
    from src.search_intelligence.control_center.next_safe_action import determine_next_safe_action

    candidate = {
        "company_key": "adesso",
        "candidate_url": "https://www.adesso.de/de/karriere/jobs/index.html",
        "status": "abort_documented",
        "gate_passed_count": 1,
        "latest_blocking_gate": "source_discovery",
        "latest_blocking_status": "failed",
        "latest_blocking_decision": "abort_documented",
        "latest_blocking_reason": "candidate URL appears to require authentication",
    }

    action = determine_next_safe_action(candidate)

    assert action.action_id == "run_initial_gate_review"
    assert action.show_action is True
    assert action.button_label == "Run source URL recovery"


def test_review_queue_recovers_technical_reachability_404() -> None:
    blocked_candidate = candidate(
        company_key="adesso",
        company_name="adesso SE",
        candidate_url="https://www.adesso.de/de/karriere/jobs/index.html",
        source_name_candidate="adesso:discovery",
        status="abort_documented",
        gate_passed_count=3,
        gate_total_count=16,
        build_status=None,
        build_recommendation=None,
        latest_blocking_gate="technical_reachability_gate",
        latest_blocking_status="failed",
        latest_blocking_decision="abort_documented",
        latest_blocking_reason="source returned HTTP 404",
    )
    html = render_control_center(
        [blocked_candidate],
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=True,
        active_tab="review-queue",
    )

    assert "Run source URL recovery" in html
    assert "Technical reachability stopped" in html
    assert "/actions/run-next-safe-action" in html
    assert 'value="run_next_safe_action"' in html


def test_review_queue_recovers_relevance_preview_stop_with_evidence_probe() -> None:
    blocked_candidate = candidate(
        company_key="adesso",
        company_name="adesso SE",
        candidate_url="https://jobs.adesso-group.com/",
        source_name_candidate="adesso:discovery",
        status="manual_review_required",
        gate_passed_count=6,
        gate_total_count=16,
        build_status=None,
        build_recommendation=None,
        latest_blocking_gate="relevance_gate",
        latest_blocking_status="manual_review_required",
        latest_blocking_decision="manual_review_required",
        latest_blocking_reason="bounded preview did not expose target-location or remote evidence",
    )
    html = render_control_center(
        [blocked_candidate],
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=True,
        active_tab="review-queue",
    )

    assert "Run autonomous relevance discovery" in html
    assert "autonomous bounded job-detail discovery" in html
    assert "/actions/run-next-safe-action" in html
    assert 'value="run_next_safe_action"' in html
