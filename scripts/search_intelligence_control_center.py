from __future__ import annotations

import html
import shlex
from dataclasses import dataclass
from typing import Iterable, Mapping

from src.search_intelligence.control_center.renderer import read_static_asset, render_template
from src.search_intelligence.control_center.view_model import build_control_center_view_model

BUILD_APPROVAL_TOKEN = "approve_connector_build"
REGISTRATION_APPROVAL_TOKEN = "approve_connector_registration"
EVIDENCE_REPAIR_TOKEN = "run_evidence_repair"


@dataclass(frozen=True)
class ControlCenterCandidate:
    candidate_id: int
    company_key: str
    company_name: str
    candidate_url: str | None
    source_name_candidate: str
    source_type_candidate: str
    status: str
    operational_risk_level: str
    false_negative_risk_level: str | None = None
    reassessment_status: str | None = None
    reassessment_reason: str | None = None
    generation_status: str | None = None
    generation_recommendation: str | None = None
    build_status: str | None = None
    build_recommendation: str | None = None
    build_mode: str | None = None
    build_next_command: str | None = None
    connector_module_path: str | None = None
    connector_test_path: str | None = None
    connector_docs_path: str | None = None
    gate_passed_count: int = 0
    gate_manual_review_count: int = 0
    gate_blocked_count: int = 0
    gate_total_count: int = 0
    latest_blocking_gate: str | None = None
    latest_blocking_reason: str | None = None
    connector_validation_status: str | None = None
    connector_validation_decision: str | None = None
    final_approval_status: str | None = None
    final_approval_decision: str | None = None

    @property
    def is_active_connector(self) -> bool:
        return self.status == "active_controlled"

    @property
    def needs_build_approval(self) -> bool:
        return self.build_status == "build_approval_required" and self.build_recommendation == "request_explicit_build_approval"

    @property
    def needs_registration_approval(self) -> bool:
        return (
            self.connector_validation_status == "passed"
            and self.connector_validation_decision == "ready_for_final_approval"
            and self.final_approval_decision != "approve_connector_registration"
            and not self.is_active_connector
        )


@dataclass(frozen=True)
class GoldMarketCoverageSummary:
    generated_at: object | None = None
    employer_origin_candidate_count: int = 0
    active_origin_connector_count: int = 0
    open_candidate_count: int = 0
    blocked_candidate_count: int = 0
    gate_reassessment_required_count: int = 0
    build_approval_required_count: int = 0
    connector_artifact_generation_allowed_count: int = 0
    high_fn_pressure_candidate_count: int = 0
    critical_fn_pressure_candidate_count: int = 0
    open_search_term_suggestion_count: int = 0
    recent_company_vocabulary_observation_count: int = 0
    recent_unregistered_company_observation_count: int = 0
    recent_new_vocabulary_term_observation_count: int = 0
    saturated_scope_count: int = 0
    actionable_novelty_scope_count: int = 0
    latest_aggregator_novelty_snapshot_at: object | None = None


@dataclass(frozen=True)
class AgentGateReview:
    candidate_id: int
    company_key: str
    company_name: str
    source_name_candidate: str
    gate_name: str
    gate_status: str
    decision: str | None = None
    stop_reason: str | None = None
    reviewed_by: str | None = None
    created_at: object | None = None


@dataclass(frozen=True)
class OrchestratorAttentionStep:
    run_id: int
    step_order: int
    step_name: str
    step_status: str
    action_mode: str
    recommendation: str
    reason: str | None = None
    metrics: Mapping[str, object] | None = None
    completed_at: object | None = None


def fallback_market_summary(candidates: list[ControlCenterCandidate]) -> GoldMarketCoverageSummary:
    return GoldMarketCoverageSummary(
        employer_origin_candidate_count=len(candidates),
        active_origin_connector_count=sum(1 for item in candidates if item.is_active_connector),
        open_candidate_count=sum(1 for item in candidates if not item.is_active_connector),
        blocked_candidate_count=sum(1 for item in candidates if item.latest_blocking_gate),
        build_approval_required_count=sum(1 for item in candidates if item.needs_build_approval),
        high_fn_pressure_candidate_count=sum(
            1 for item in candidates if item.false_negative_risk_level in {"critical", "high"}
        ),
        critical_fn_pressure_candidate_count=sum(
            1 for item in candidates if item.false_negative_risk_level == "critical"
        ),
    )


def h(value: object) -> str:
    return html.escape(str(value), quote=True)


def humanize(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "-"
    special = {
        "active_controlled": "Active controlled",
        "manual_review_required": "Needs review",
        "build_approval_required": "Build approval required",
        "artifact_generation_allowed": "Artifact generation allowed",
        "artifacts_present": "Artifacts present",
        "gate_reassessment_required": "Gate reassessment required",
        "request_explicit_build_approval": "Request explicit build approval",
        "bounded_investigation_connector": "Bounded investigation connector",
        "connector_candidate_from_gate_evidence": "Connector candidate from gate evidence",
        "origin_validation_ground_truth": "Origin validation / ground truth",
        "employer_origin_career_site": "Employer-origin career site",
        "employer_origin_ats_backed_career_site": "Employer-origin ATS-backed career site",
        "detail_evidence_gate": "Detail evidence gate",
    }
    return special.get(raw, raw.replace("_", " ").replace("-", " ").strip().capitalize())


def risk_class(value: str | None) -> str:
    raw = (value or "").lower()
    if raw in {"critical", "high", "blocked"}:
        return "bad"
    if raw in {"medium", "manual_review_required", "build_approval_required", "open"}:
        return "warn"
    if raw in {"low", "passed", "active_controlled"}:
        return "ok"
    return "neutral"


def build_approval_command(company_key: str, reviewed_by: str) -> tuple[str, ...]:
    return (
        "python",
        "-m",
        "scripts.run_approval_gated_connector_build_agent",
        "--company-key",
        company_key,
        "--reviewed-by",
        reviewed_by,
        "--approve-build",
        "--write",
    )


def registration_approval_command(company_key: str, target_location: str, reviewed_by: str) -> tuple[str, ...]:
    return (
        "python",
        "-m",
        "scripts.run_employer_origin_agent_chain",
        "--company-key",
        company_key,
        "--target-location",
        target_location,
        "--reviewed-by",
        reviewed_by,
        "--approval-token",
        REGISTRATION_APPROVAL_TOKEN,
    )


def evidence_repair_command(company_key: str, target_location: str, reviewed_by: str) -> tuple[str, ...]:
    return (
        "python",
        "-m",
        "scripts.run_employer_origin_agent_chain",
        "--company-key",
        company_key,
        "--target-location",
        target_location,
        "--reviewed-by",
        reviewed_by,
        "--attempt-repair",
    )


def chain_steps(candidate: ControlCenterCandidate) -> tuple[tuple[str, str, str], ...]:
    learning_state = "done" if candidate.false_negative_risk_level or candidate.reassessment_status else "open"
    origin_state = "blocked" if candidate.latest_blocking_gate == "detail_evidence_gate" else "done"
    if candidate.build_status in {"build_approval_required", "gate_reassessment_required"}:
        build_state = "current"
    elif candidate.build_status in {"artifact_generation_allowed", "artifacts_present"} or candidate.connector_module_path:
        build_state = "done"
    else:
        build_state = "open"
    validation_state = "done" if candidate.connector_validation_status == "passed" else "open"
    approval_state = "current" if candidate.needs_registration_approval else "done" if candidate.final_approval_decision == "approve_connector_registration" else "open"
    active_state = "done" if candidate.is_active_connector else "open"
    return (
        ("Discovered", "done", "Company exists as DB-backed source candidate."),
        ("Candidate", "done", humanize(candidate.status)),
        ("Learning", learning_state, humanize(candidate.false_negative_risk_level or candidate.reassessment_status or "open")),
        ("Origin", origin_state, humanize(candidate.latest_blocking_gate or "gates reviewed")),
        ("Build", build_state, humanize(candidate.build_status or "not_started")),
        ("Validate", validation_state, humanize(candidate.connector_validation_decision or candidate.connector_validation_status or "open")),
        ("Approval", approval_state, humanize(candidate.final_approval_decision or candidate.final_approval_status or "open")),
        ("Active", active_state, humanize(candidate.status if candidate.is_active_connector else "not_active")),
    )


def current_stage(candidate: ControlCenterCandidate) -> str:
    if candidate.is_active_connector:
        return "Active connector"
    if candidate.needs_registration_approval:
        return "Registration approval"
    if candidate.needs_build_approval:
        return "Build approval"
    if candidate.latest_blocking_gate:
        return humanize(candidate.latest_blocking_gate)
    return humanize(candidate.status)


def candidate_sort_key(candidate: ControlCenterCandidate) -> tuple[int, int, str]:
    priority = 0 if candidate.needs_build_approval or candidate.needs_registration_approval else 1
    pressure = 0 if candidate.false_negative_risk_level in {"critical", "high"} else 1
    return (priority, pressure, candidate.company_name.lower())


def render_chain(candidate: ControlCenterCandidate) -> str:
    items = []
    for label, state, title in chain_steps(candidate):
        items.append(f"<li class='{h(state)}' title='{h(title)}'><span></span>{h(label)}</li>")
    return f"<ol class='chain' aria-label='Discovery to controlled activation chain'>{''.join(items)}</ol>"


def render_candidate_card(
    candidate: ControlCenterCandidate,
    *,
    reviewed_by: str,
    target_location: str,
    write_actions_enabled: bool,
    compact: bool = False,
) -> str:
    build_form = ""
    if candidate.needs_build_approval and not compact:
        cmd = shlex.join(build_approval_command(candidate.company_key, reviewed_by))
        disabled = "disabled" if not write_actions_enabled else ""
        hint = "" if write_actions_enabled else "<p class='warning'>Start the UI with <code>--allow-write-actions</code> to approve builds.</p>"
        build_form = (
            "<div class='action-panel'>"
            "<strong>Build approval</strong>"
            "<p>Allows connector artifacts only. Registration, activation, Bronze writes and scheduler changes stay blocked.</p>"
            f"<details class='command-box'><summary>Show approval command</summary><pre>{h(cmd)}</pre></details>"
            f"{hint}"
            "<form method='post' action='/actions/approve-build'>"
            f"<input type='hidden' name='company_key' value='{h(candidate.company_key)}'>"
            f"<label>Approval token <input name='approval_token' placeholder='{h(BUILD_APPROVAL_TOKEN)}' autocomplete='off'></label>"
            f"<label>Reviewed by <input name='reviewed_by' value='{h(reviewed_by)}'></label>"
            f"<button type='submit' {disabled}>Approve connector build</button>"
            "</form>"
            "</div>"
        )

    registration_form = ""
    if candidate.needs_registration_approval and not compact:
        cmd = shlex.join(registration_approval_command(candidate.company_key, target_location, reviewed_by))
        disabled = "disabled" if not write_actions_enabled else ""
        registration_form = (
            "<div class='action-panel registration'>"
            "<strong>Registration approval</strong>"
            "<p>Approves registration gate only. Controlled activation remains separate.</p>"
            f"<details class='command-box'><summary>Show registration command</summary><pre>{h(cmd)}</pre></details>"
            "<form method='post' action='/actions/approve-registration'>"
            f"<input type='hidden' name='company_key' value='{h(candidate.company_key)}'>"
            f"<label>Approval token <input name='approval_token' placeholder='{h(REGISTRATION_APPROVAL_TOKEN)}' autocomplete='off'></label>"
            f"<label>Reviewed by <input name='reviewed_by' value='{h(reviewed_by)}'></label>"
            f"<button type='submit' {disabled}>Approve registration gate</button>"
            "</form>"
            "</div>"
        )

    blocker = ""
    if candidate.latest_blocking_gate:
        blocker = f"<p class='blocker'><strong>{h(humanize(candidate.latest_blocking_gate))}:</strong> {h(candidate.latest_blocking_reason or '-') }</p>"

    artifacts = ""
    artifact_items = [candidate.connector_module_path, candidate.connector_test_path, candidate.connector_docs_path]
    if any(artifact_items) and not compact:
        artifacts = "<ul class='artifacts'>" + "".join(f"<li>{h(item or '-')}</li>" for item in artifact_items) + "</ul>"

    pressure_label = humanize(candidate.false_negative_risk_level or "-")
    return (
        f"<article class='candidate-card {h(risk_class(candidate.false_negative_risk_level or candidate.status))}'>"
        "<header>"
        f"<div><h3>{h(candidate.company_name)}</h3><p>{h(candidate.company_key)} · {h(candidate.source_name_candidate)}</p></div>"
        f"<span class='pill {h(risk_class(candidate.status))}'>{h(humanize(candidate.status))}</span>"
        "</header>"
        f"{render_chain(candidate)}"
        "<div class='facts'>"
        f"<span>stage <strong>{h(current_stage(candidate))}</strong></span>"
        f"<span>source type <strong>{h(humanize(candidate.source_type_candidate))}</strong></span>"
        f"<span>FN pressure <strong>{h(pressure_label)}</strong></span>"
        f"<span>gates <strong>{h(candidate.gate_passed_count)}/{h(candidate.gate_total_count)} passed</strong></span>"
        "</div>"
        f"<p class='next-step'>{h(next_step_text(candidate))}</p>"
        f"{blocker}"
        f"{artifacts}"
        f"{build_form}"
        f"{registration_form}"
        "</article>"
    )


def next_step_text(candidate: ControlCenterCandidate) -> str:
    if candidate.is_active_connector:
        return "Monitor connector health and incremental source contribution."
    if candidate.needs_registration_approval:
        return "Review validation evidence and approve registration gate."
    if candidate.needs_build_approval:
        return "Review bounded investigation scope and approve connector artifact build."
    if candidate.latest_blocking_gate:
        return "Resolve the blocking gate before connector registration."
    return "Continue gate review."


def kpi(label: str, value: object, helper: str, cls: str = "neutral") -> str:
    return f"<div class='metric {h(cls)}'><span class='eyebrow'>{h(label)}</span><strong>{h(value)}</strong><small>{h(helper)}</small></div>"


def render_lifecycle_bars(candidates: list[ControlCenterCandidate]) -> str:
    total = max(len(candidates), 1)
    active = sum(1 for c in candidates if c.is_active_connector)
    blocked = sum(1 for c in candidates if c.latest_blocking_gate)
    approvals = sum(1 for c in candidates if c.needs_build_approval or c.needs_registration_approval)
    rows = (("Candidates", len(candidates)), ("Active", active), ("Blocked", blocked), ("Approvals", approvals))
    rendered = []
    for label, value in rows:
        width = max(6, round((value / total) * 100))
        rendered.append(f"<div class='bar-row'><span>{h(label)}</span><div><i style='width:{h(width)}%'></i></div><b>{h(value)}</b></div>")
    return "<div class='funnel'>" + "".join(rendered) + "</div>"


def render_active_connectors(candidates: Iterable[ControlCenterCandidate]) -> str:
    active = [item for item in candidates if item.is_active_connector]
    if not active:
        return "<section class='panel'><h2>Active Connectors</h2><p class='muted'>No active controlled employer-origin connector is registered yet.</p></section>"
    rows = []
    for item in active:
        rows.append(
            "<tr>"
            f"<td><strong>{h(item.company_name)}</strong><br><span>{h(item.company_key)}</span></td>"
            f"<td>{h(item.source_name_candidate)}</td>"
            f"<td>{h(humanize(item.source_type_candidate))}</td>"
            f"<td><span class='pill ok'>{h(humanize(item.status))}</span></td>"
            f"<td>{h(item.gate_passed_count)}/{h(item.gate_total_count)}</td>"
            "</tr>"
        )
    return (
        "<section class='panel'><div class='section-head'><div><span class='eyebrow'>Operational Surface</span>"
        "<h2>Active Connectors</h2></div>"
        f"<span class='pill ok'>{h(len(active))} active</span></div>"
        "<table class='compact-table'><thead><tr><th>Company</th><th>Source</th><th>Type</th><th>Status</th><th>Gates</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></section>"
    )


def render_build_approvals(candidates: Iterable[ControlCenterCandidate], *, reviewed_by: str, target_location: str, write_actions_enabled: bool) -> str:
    items = [item for item in candidates if item.needs_build_approval or item.needs_registration_approval]
    if not items:
        return "<section class='panel'><h2>Connector Approvals</h2><p class='muted'>No connector build or registration approval is waiting.</p></section>"
    cards = [render_candidate_card(item, reviewed_by=reviewed_by, target_location=target_location, write_actions_enabled=write_actions_enabled) for item in items]
    return (
        "<section class='panel'><div class='section-head'><div><span class='eyebrow'>Approval Control</span>"
        "<span class='eyebrow'>Approval control</span>"
        "<h1>Connector Build & Registration Approvals</h2></div>"
        f"<span class='pill warn'>{h(len(items))} item(s)</span></div>"
        "<p class='muted'>Build approval may create connector artifacts only. Registration and activation remain separate gates.</p>"
        f"<div class='card-grid single'>{''.join(cards)}</div></section>"
    )


def render_candidate_chain(candidates: Iterable[ControlCenterCandidate], *, reviewed_by: str, target_location: str, write_actions_enabled: bool) -> str:
    items = sorted(list(candidates), key=candidate_sort_key)
    if not items:
        return "<section class='panel'><h2>Candidate Chain</h2><p class='muted'>No employer-origin candidates found.</p></section>"
    cards = [render_candidate_card(item, reviewed_by=reviewed_by, target_location=target_location, write_actions_enabled=write_actions_enabled, compact=True) for item in items]
    return (
        "<section class='panel'><div class='section-head'><div><span class='eyebrow'>System Chain</span>"
        "<h2>Discovery → Candidate → Origin Exploration → Connector → Approval</h2></div>"
        f"<span class='pill neutral'>{h(len(items))} candidates</span></div>"
        "<p class='muted'>Discovery creates a candidate. Search Intelligence creates pressure. Agents explore origin sources. Connector artifacts and registration require explicit approval.</p>"
        f"<div class='card-grid'>{''.join(cards)}</div></section>"
    )


def render_health(candidates: list[ControlCenterCandidate]) -> str:
    blockers = [item for item in candidates if item.latest_blocking_gate]
    critical = [item for item in candidates if item.false_negative_risk_level == "critical"]
    rows = []
    for item in sorted(candidates, key=candidate_sort_key):
        diagnosis = item.latest_blocking_reason or ("Monitor connector health and source contribution." if item.is_active_connector else "No concrete blocker recorded.")
        rows.append(
            "<tr>"
            f"<td><strong>{h(item.company_name)}</strong><br><span>{h(item.company_key)}</span></td>"
            f"<td><span class='pill {h(risk_class(item.status))}'>{h(humanize(item.status))}</span></td>"
            f"<td>{h(current_stage(item))}</td>"
            f"<td>{h(diagnosis)}</td>"
            "</tr>"
        )
    return (
        "<section class='tab-view' data-view='health'><div class='view-head'><span class='eyebrow'>Heartbeat & Health</span><h1>System health and diagnostics</h1>"
        "<p class='muted'>Shows not only whether something is blocked, but why and what the next useful action is.</p></div>"
        "<section class='kpis'>"
        f"{kpi('Blocking reasons', len(blockers), 'candidates with concrete blocker', 'warn')}"
        f"{kpi('Critical pressure', len(critical), 'false-negative signals', 'bad')}"
        f"{kpi('Candidates', len(candidates), 'known employer-origin candidates', 'neutral')}"
        "</section><section class='panel'><h2>Connector and candidate diagnostics</h2>"
        "<table><thead><tr><th>Company</th><th>Status</th><th>Current stage</th><th>Diagnosis</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></section></section>"
    )


def render_orchestrator_attention_summary(orchestrator_steps: list[OrchestratorAttentionStep], *, compact: bool = False) -> str:
    if not orchestrator_steps:
        return (
            "<section class='panel orchestrator-panel'><div class='section-head'><div>"
            "<span class='eyebrow'>Nightly Intelligence Cycle</span><h2>No attention steps</h2></div>"
            "<span class='pill ok'>clear</span></div>"
            "<p class='muted'>No latest orchestrator attention steps are visible yet. Run the S7F orchestrator with --write to persist a fresh audit.</p></section>"
        )
    rows = []
    for step in orchestrator_steps[:3 if compact else 20]:
        rows.append(
            "<article class='attention-step'>"
            f"<span class='pill {h(risk_class(step.step_status))}'>{h(humanize(step.step_status))}</span>"
            f"<h3>{h(humanize(step.step_name))}</h3>"
            f"<p>{h(step.recommendation)}</p>"
            f"<small>mode: {h(humanize(step.action_mode))} · run #{h(step.run_id)}</small>"
            "</article>"
        )
    more = len(orchestrator_steps) - len(rows)
    more_note = f"<p class='muted'>{h(more)} more attention step(s) available in the Orchestrator tab.</p>" if more > 0 else ""
    return (
        "<section class='panel orchestrator-panel'><div class='section-head'><div>"
        "<span class='eyebrow'>Nightly Intelligence Cycle</span><h2>Attention required</h2></div>"
        f"<span class='pill warn'>{h(len(orchestrator_steps))} step(s)</span></div>"
        f"<div class='attention-list'>{''.join(rows)}</div>{more_note}</section>"
    )


def render_dashboard(
    candidates: list[ControlCenterCandidate],
    *,
    reviewed_by: str,
    target_location: str,
    write_actions_enabled: bool,
    market_summary: GoldMarketCoverageSummary,
    orchestrator_steps: list[OrchestratorAttentionStep],
) -> str:
    priority = sorted(candidates, key=candidate_sort_key)[:3]
    cards = [render_candidate_card(item, reviewed_by=reviewed_by, target_location=target_location, write_actions_enabled=write_actions_enabled, compact=True) for item in priority]
    return (
        "<section class='tab-view' data-view='dashboard'><div class='view-head'><span class='eyebrow'>Dashboard</span><h1>Search Intelligence Overview</h1>"
        "<p class='muted'>One-page summary of market coverage, connector readiness, health blockers, approvals and nightly cycle attention.</p></div>"
        "<section class='dashboard-grid'>"
        "<div class='panel'><span class='eyebrow'>Gold Market Coverage</span><h2>Candidate lifecycle</h2>"
        + render_lifecycle_bars(candidates)
        + "<div class='facts'>"
        + f"<span>open candidates <strong>{h(market_summary.open_candidate_count)}</strong></span>"
        + f"<span>term suggestions <strong>{h(market_summary.open_search_term_suggestion_count)}</strong></span>"
        + f"<span>vocabulary observations <strong>{h(market_summary.recent_company_vocabulary_observation_count)}</strong></span>"
        + f"<span>unregistered companies <strong>{h(market_summary.recent_unregistered_company_observation_count)}</strong></span>"
        + "</div></div>"
        "<div class='panel'><span class='eyebrow'>Needs Attention</span><h2>Priority candidates</h2>" + "".join(cards) + "</div>"
        + render_orchestrator_attention_summary(orchestrator_steps, compact=True)
        + "</section></section>"
    )


def render_connectors_tab(candidates: list[ControlCenterCandidate], *, reviewed_by: str, target_location: str, write_actions_enabled: bool) -> str:
    return (
        "<section class='tab-view' data-view='connectors'><div class='view-head'><span class='eyebrow'>Connectors & Candidates</span><h1>Connector lifecycle workspace</h1>"
        "<p class='muted'>Active connectors, unresolved candidates, current stage, blocker and next action in one operational view.</p></div>"
        f"{render_active_connectors(candidates)}{render_candidate_chain(candidates, reviewed_by=reviewed_by, target_location=target_location, write_actions_enabled=write_actions_enabled)}</section>"
    )


def render_approvals_tab(candidates: list[ControlCenterCandidate], *, reviewed_by: str, target_location: str, write_actions_enabled: bool) -> str:
    return (
        "<section class='tab-view' data-view='approvals'><div class='view-head'><span class='eyebrow'>Approvals</span><h1>Approval workspace</h1>"
        "<p class='muted'>Approve connector artifact builds and later registration gates from the GUI. No auto-PR, source activation, Bronze writes or scheduler changes.</p></div>"
        f"{render_build_approvals(candidates, reviewed_by=reviewed_by, target_location=target_location, write_actions_enabled=write_actions_enabled)}</section>"
    )


def render_gap_tab() -> str:
    return (
        "<section class='tab-view' data-view='gaps'><div class='view-head'><span class='eyebrow'>Gap Analysis</span><h1>Market demand and capability gaps</h1>"
        "<p class='muted'>Gold-backed view planned next: market terms, observed skills, profile fit and concrete improvement signals.</p></div>"
        "<section class='empty-state'><h2>Gold layer needed</h2><p>This tab should not invent analytics from raw agent output. It is intentionally waiting for the Search Intelligence Gold model.</p></section></section>"
    )


def render_jobs_tab() -> str:
    return (
        "<section class='tab-view' data-view='jobs'><div class='view-head'><span class='eyebrow'>Jobs & Applications</span><h1>New jobs and application drafts</h1>"
        "<p class='muted'>Planned product view: new jobs, top matches and AI-assisted application drafts ready for review.</p></div>"
        "<section class='empty-state'><h2>Application workflow placeholder</h2><p>Needs Gold job ranking plus a separate approval-safe application draft workflow.</p></section></section>"
    )



def render_demo_rule_cycle_visual() -> str:
    """Render a demo-oriented Search Intelligence rule-cycle visual.

    This is intentionally HTML/CSS-only: no external assets, no JavaScript,
    no hidden pipeline side effects. It visualizes the existing control loop
    until the Gold/UI model can provide richer dashboard-native metrics.
    """
    steps = [
        (
            "Explore",
            "Aggregator discovery",
            "Read bounded market signals, company sightings and term evidence without bypassing defensive limits.",
            "StepStone / source probes",
        ),
        (
            "Learn",
            "Search Intelligence",
            "Classify novelty, search-term value, company vocabulary and false-negative pressure.",
            "Gold coverage metrics",
        ),
        (
            "Gate",
            "Origin Source Discovery",
            "Select a plausible HTTPS employer-origin source or stop for manual review when ambiguous.",
            "Discovery gate",
        ),
        (
            "Build",
            "Connector candidate",
            "Generate bounded connector artifacts only after explicit approval; no registration or activation yet.",
            "Approval token",
        ),
        (
            "Validate",
            "Controlled source",
            "Validate gates, evidence, incremental uniqueness and operational health before controlled use.",
            "Health + lifecycle",
        ),
        (
            "Improve",
            "Feedback loop",
            "Feed misses, blockers and new vocabulary back into search profiles and market coverage analysis.",
            "Next cycle",
        ),
    ]
    cards = []
    for index, (verb, title, body, tag) in enumerate(steps, start=1):
        cards.append(
            "<article class='cycle-card'>"
            f"<div class='cycle-index'>{index:02d}</div>"
            f"<span class='eyebrow'>{verb}</span>"
            f"<h3>{title}</h3>"
            f"<p>{body}</p>"
            f"<div class='cycle-tag'>{tag}</div>"
            "</article>"
        )
    return (
        "<section class='panel demo-cycle-panel'>"
        "<div class='cycle-header'>"
        "<div><span class='eyebrow'>Intelligent product loop</span>"
        "<h2>Market signal → origin source → connector → feedback</h2>"
        "<p class='muted'>Demo framing: this is not just a crawler. It is a gated learning loop that turns market evidence into controlled connector decisions.</p>"
        "</div>"
        "<div class='cycle-orbit' aria-hidden='true'><span></span><strong>SI</strong></div>"
        "</div>"
        f"<div class='rule-cycle-grid'>{''.join(cards)}</div>"
        "<div class='guardrail-strip'>"
        "<span>No auto-PR</span><span>No source activation</span><span>No Bronze write</span><span>No scheduler change</span><span>Explicit approval gates</span>"
        "</div>"
        "</section>"
    )


def render_orchestrator_tab(orchestrator_steps: list[OrchestratorAttentionStep]) -> str:
    return (
        "<section class='tab-view' data-view='orchestrator'><div class='view-head'><span class='eyebrow'>Orchestrator</span><h1>Nightly Intelligence Cycle Attention</h1>"
        "<p class='muted'>Latest persisted S7F orchestrator steps that require attention before the next automated cycle.</p></div>"
        f"{render_orchestrator_attention_summary(orchestrator_steps)}"
        "<section class='panel'><div class='section-head'><div><span class='eyebrow'>Manual run command</span><h2>Refresh the cycle audit</h2></div><span class='pill neutral'>audit-only</span></div>"
        "<pre>python -m scripts.run_nightly_search_intelligence_orchestrator --reviewed-by jens --write</pre>"
        "<p class='muted'>This command persists only orchestrator run/step audit data. It does not register connectors, activate sources, write Bronze records or change scheduler configuration.</p></section></section>"
    )


def render_demo_chain_tab(candidates: list[ControlCenterCandidate], *, reviewed_by: str, target_location: str, write_actions_enabled: bool) -> str:
    return (
        "<section class='tab-view' data-view='demo'><div class='view-head'><span class='eyebrow'>Demo Chain</span><h1>Discovered company → approved connector</h1>"
        "<p class='muted'>The end-to-end story for the demo: discovery, candidate, learning pressure, origin exploration, connector build approval and registration gate.</p></div>"
        f"{render_demo_rule_cycle_visual()}"
        f"{render_candidate_chain(candidates, reviewed_by=reviewed_by, target_location=target_location, write_actions_enabled=write_actions_enabled)}</section>"
    )


def nav_item(tab: str, label: str, count: int | None = None, *, active_tab: str = "dashboard") -> str:
    badge = f"<b>{h(count)}</b>" if count is not None else ""
    active = " active" if tab == active_tab else ""
    return f"<a class='nav-link{active}' data-tab-link='{h(tab)}' href='/?tab={h(tab)}'>{h(label)}{badge}</a>"


def render_control_center(
    candidates: list[ControlCenterCandidate],
    *,
    reviewed_by: str,
    target_location: str,
    write_actions_enabled: bool,
    flash_message: str | None = None,
    active_tab: str = "dashboard",
    market_summary: GoldMarketCoverageSummary | None = None,
    orchestrator_steps: list[OrchestratorAttentionStep] | None = None,
    gate_reviews: list[AgentGateReview] | None = None,
) -> str:
    market_summary = market_summary or fallback_market_summary(candidates)
    orchestrator_steps = orchestrator_steps or []
    gate_reviews = gate_reviews or []

    tab_aliases = {
        "connectors": "review-queue",
        "approvals": "review-queue",
    }
    active_tab = tab_aliases.get(active_tab, active_tab)

    allowed_tabs = {"dashboard", "health", "review-queue", "connectors", "approvals", "orchestrator", "agent-monitor", "gaps", "jobs", "demo-chain"}
    if active_tab not in allowed_tabs:
        active_tab = "dashboard"

    legacy_view_html = ""
    if active_tab == "health":
        legacy_view_html = render_health(candidates)
    elif active_tab == "connectors":
        legacy_view_html = render_connectors_tab(
            candidates,
            reviewed_by=reviewed_by,
            target_location=target_location,
            write_actions_enabled=write_actions_enabled,
        )
    elif active_tab == "approvals":
        legacy_view_html = render_approvals_tab(
            candidates,
            reviewed_by=reviewed_by,
            target_location=target_location,
            write_actions_enabled=write_actions_enabled,
        )
    elif active_tab == "orchestrator":
        legacy_view_html = render_orchestrator_tab(orchestrator_steps)
    elif active_tab == "gaps":
        legacy_view_html = render_gap_tab()
    elif active_tab == "jobs":
        legacy_view_html = render_jobs_tab()
    elif active_tab == "demo-chain":
        legacy_view_html = render_demo_chain_tab(
            candidates,
            reviewed_by=reviewed_by,
            target_location=target_location,
            write_actions_enabled=write_actions_enabled,
        )

    return render_template(
        "app.html",
        build_control_center_view_model(
            candidates,
            active_tab=active_tab,
            market_summary=market_summary,
            orchestrator_steps=orchestrator_steps,
            gate_reviews=gate_reviews,
            write_actions_enabled=write_actions_enabled,
            legacy_view_html=legacy_view_html,
            stylesheet=read_static_asset("control_center.css"),
            flash_message=flash_message,
        ),
    )
