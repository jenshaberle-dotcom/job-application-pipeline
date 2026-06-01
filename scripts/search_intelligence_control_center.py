from __future__ import annotations

import html
import shlex
from dataclasses import dataclass
from typing import Iterable

BUILD_APPROVAL_TOKEN = "approve_connector_build"
REGISTRATION_APPROVAL_TOKEN = "approve_connector_registration"


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


def render_dashboard(
    candidates: list[ControlCenterCandidate],
    *,
    reviewed_by: str,
    target_location: str,
    write_actions_enabled: bool,
    market_summary: GoldMarketCoverageSummary,
) -> str:
    priority = sorted(candidates, key=candidate_sort_key)[:3]
    cards = [render_candidate_card(item, reviewed_by=reviewed_by, target_location=target_location, write_actions_enabled=write_actions_enabled, compact=True) for item in priority]
    return (
        "<section class='tab-view' data-view='dashboard'><div class='view-head'><span class='eyebrow'>Dashboard</span><h1>Search Intelligence Overview</h1>"
        "<p class='muted'>One-page summary of market coverage, connector readiness, health blockers and approvals.</p></div>"
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
        "</section></section>"
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


def render_demo_chain_tab(candidates: list[ControlCenterCandidate], *, reviewed_by: str, target_location: str, write_actions_enabled: bool) -> str:
    return (
        "<section class='tab-view' data-view='demo'><div class='view-head'><span class='eyebrow'>Demo Chain</span><h1>Discovered company → approved connector</h1>"
        "<p class='muted'>The end-to-end story for the demo: discovery, candidate, learning pressure, origin exploration, connector build approval and registration gate.</p></div>"
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
) -> str:
    market_summary = market_summary or fallback_market_summary(candidates)
    active_count = market_summary.active_origin_connector_count
    build_approval_count = market_summary.build_approval_required_count
    registration_approval_count = sum(1 for item in candidates if item.needs_registration_approval)
    critical_count = market_summary.critical_fn_pressure_candidate_count
    mode = "write-enabled" if write_actions_enabled else "read-only"
    flash = f"<div class='flash'>{h(flash_message)}</div>" if flash_message else ""
    allowed_tabs = {"dashboard", "health", "connectors", "approvals", "gaps", "jobs", "demo-chain"}
    if active_tab not in allowed_tabs:
        active_tab = "dashboard"
    active_view_html = {
        "dashboard": render_dashboard(
            candidates,
            reviewed_by=reviewed_by,
            target_location=target_location,
            write_actions_enabled=write_actions_enabled,
            market_summary=market_summary,
        ),
        "health": render_health(candidates),
        "connectors": render_connectors_tab(candidates, reviewed_by=reviewed_by, target_location=target_location, write_actions_enabled=write_actions_enabled),
        "approvals": render_approvals_tab(candidates, reviewed_by=reviewed_by, target_location=target_location, write_actions_enabled=write_actions_enabled),
        "gaps": render_gap_tab(),
        "jobs": render_jobs_tab(),
        "demo-chain": render_demo_chain_tab(candidates, reviewed_by=reviewed_by, target_location=target_location, write_actions_enabled=write_actions_enabled),
    }[active_tab]
    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Search Intelligence Control Center</title>
<style>
:root {{
  color-scheme: dark;
  --bg:#020812; --bg2:#041321; --panel:rgba(8,24,39,.94); --panel2:rgba(12,38,60,.72);
  --line:rgba(99,159,199,.30); --line2:rgba(99,159,199,.18); --text:#ecf7ff; --muted:#9db8cc;
  --cyan:#22d3ee; --green:#70e36b; --amber:#f5b642; --red:#ff5d5d; --blue:#65b7ff;
  --sidebar:244px; --radius:18px; --shadow:0 20px 70px rgba(0,0,0,.38);
}}
* {{ box-sizing:border-box; }}
html, body {{ width:100%; min-height:100%; margin:0; overflow-x:hidden; }}
body {{ font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif; color:var(--text); background:radial-gradient(circle at 12% 0%, rgba(34,211,238,.16), transparent 30%), linear-gradient(135deg, var(--bg2), var(--bg) 70%); }}
.app-shell {{ display:grid; grid-template-columns:var(--sidebar) minmax(0,1fr); min-height:100vh; width:100%; }}
.sidebar {{ position:sticky; top:0; height:100vh; overflow-y:auto; padding:1.15rem .85rem; border-right:1px solid var(--line); background:linear-gradient(180deg, rgba(5,19,32,.98), rgba(3,11,21,.98)); }}
.logo .eyebrow {{ display:block; margin-bottom:.35rem; }} .logo h1 {{ font-size:1.05rem; margin:.1rem 0 0; }} .logo p {{ margin:.1rem 0 1.2rem; color:var(--muted); }}
.nav {{ display:grid; gap:.55rem; }} .nav-link {{ display:flex; align-items:center; justify-content:space-between; gap:.6rem; padding:.68rem .75rem; color:var(--text); text-decoration:none; border:1px solid var(--line); border-radius:11px; background:rgba(255,255,255,.025); font-weight:700; }} .nav-link:hover,.nav-link.active {{ border-color:rgba(34,211,238,.75); background:rgba(34,211,238,.13); }} .nav-link b {{ min-width:1.45rem; height:1.45rem; display:inline-grid; place-items:center; border-radius:999px; background:var(--cyan); color:#03101d; }}
.sidebar-footer {{ position:absolute; left:.85rem; right:.85rem; bottom:.8rem; display:grid; gap:.45rem; }}
.content {{ min-width:0; width:100%; padding:2rem clamp(1.5rem,2.4vw,3rem) 3rem; }}
.content-inner {{ width:100%; max-width:1480px; }}
.view-head {{ max-width:980px; margin-bottom:1.1rem; }} h1 {{ margin:0; font-size:clamp(1.7rem,2vw,2.35rem); letter-spacing:.01em; }} h2,h3 {{ margin:.1rem 0; }} p {{ line-height:1.45; }} .muted {{ color:var(--muted); }} .eyebrow {{ color:var(--cyan); text-transform:uppercase; letter-spacing:.13em; font-size:.72rem; font-weight:800; }}
.mode,.pill {{ display:inline-flex; align-items:center; border:1px solid var(--line); border-radius:999px; padding:.34rem .62rem; font-size:.82rem; white-space:nowrap; }} .mode {{ color:var(--cyan); background:rgba(34,211,238,.1); }} .pill.ok {{ color:var(--green); border-color:rgba(112,227,107,.44); }} .pill.warn {{ color:var(--amber); border-color:rgba(245,182,66,.52); }} .pill.bad {{ color:var(--red); border-color:rgba(255,93,93,.50); }} .pill.neutral {{ color:var(--muted); }}
.kpi-strip,.kpis {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:1rem; margin:0 0 1rem; }} .metric,.panel,.candidate-card,.empty-state {{ background:linear-gradient(180deg,var(--panel),rgba(5,16,29,.96)); border:1px solid var(--line); border-radius:var(--radius); box-shadow:var(--shadow); }} .metric {{ padding:1rem 1.1rem; }} .metric strong {{ display:block; margin:.18rem 0; font-size:1.55rem; }} .metric small {{ color:var(--muted); }} .metric.ok {{ border-color:rgba(112,227,107,.48); }} .metric.warn {{ border-color:rgba(245,182,66,.52); }} .metric.bad {{ border-color:rgba(255,93,93,.52); }}
.tab-view {{ display:block; }}
.dashboard-grid {{ display:grid; grid-template-columns:minmax(360px,.72fr) minmax(620px,1.28fr); gap:1rem; align-items:start; }}
.panel,.empty-state {{ padding:1rem; }} .section-head {{ display:flex; justify-content:space-between; gap:1rem; align-items:start; margin-bottom:.75rem; }}
.funnel {{ display:grid; gap:.7rem; margin-top:1rem; }} .bar-row {{ display:grid; grid-template-columns:100px minmax(0,1fr) 32px; align-items:center; gap:.75rem; }} .bar-row span {{ font-weight:700; }} .bar-row div {{ height:.55rem; border:1px solid var(--line); border-radius:999px; overflow:hidden; background:rgba(255,255,255,.03); }} .bar-row i {{ display:block; height:100%; background:linear-gradient(90deg,var(--cyan),var(--blue)); border-radius:999px; }} .bar-row b {{ text-align:right; }}
.card-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(430px,1fr)); gap:1rem; }} .card-grid.single {{ grid-template-columns:1fr; }}
.candidate-card {{ padding:1rem; border-left:4px solid var(--line); }} .candidate-card.bad {{ border-left-color:var(--red); }} .candidate-card.warn {{ border-left-color:var(--amber); }} .candidate-card.ok {{ border-left-color:var(--green); }} .candidate-card header {{ display:flex; justify-content:space-between; gap:.75rem; align-items:start; }} .candidate-card header p {{ margin:.15rem 0 0; color:var(--muted); }}
.chain {{ list-style:none; padding:0; margin:.9rem 0; display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.45rem; }} .chain li {{ border:1px solid var(--line); border-radius:999px; padding:.37rem .48rem; font-size:.78rem; color:var(--muted); display:flex; gap:.36rem; align-items:center; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }} .chain li span {{ flex:0 0 .52rem; width:.52rem; height:.52rem; border-radius:999px; background:var(--muted); }} .chain li.done {{ color:var(--green); border-color:rgba(112,227,107,.32); }} .chain li.done span {{ background:var(--green); }} .chain li.current {{ color:var(--amber); border-color:rgba(245,182,66,.50); }} .chain li.current span {{ background:var(--amber); }} .chain li.blocked {{ color:var(--red); border-color:rgba(255,93,93,.5); }} .chain li.blocked span {{ background:var(--red); }}
.facts {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.5rem; margin:.65rem 0; }} .facts span {{ color:var(--muted); background:rgba(255,255,255,.025); border:1px solid var(--line); border-radius:10px; padding:.5rem; min-width:0; overflow:hidden; text-overflow:ellipsis; }} .facts strong {{ color:var(--text); }} .next-step {{ color:#d8f4ff; }} .blocker {{ border-left:3px solid var(--amber); padding-left:.65rem; color:#f8ddb0; }} .artifacts {{ margin:.5rem 0; color:var(--muted); }}
.action-panel {{ margin-top:.8rem; padding:.85rem; border:1px solid rgba(245,182,66,.38); border-radius:13px; background:rgba(245,182,66,.08); }} .action-panel.registration {{ border-color:rgba(34,211,238,.42); background:rgba(34,211,238,.08); }} pre {{ white-space:pre-wrap; overflow:auto; padding:.65rem; border-radius:10px; border:1px solid var(--line); background:#03101d; color:#d8f4ff; }} form {{ display:flex; gap:.55rem; flex-wrap:wrap; align-items:end; }} label {{ display:grid; gap:.25rem; color:var(--muted); font-size:.84rem; }} input {{ background:#061522; color:var(--text); border:1px solid var(--line); border-radius:10px; padding:.48rem .58rem; }} button {{ background:linear-gradient(135deg,#13b7d2,#1d78c1); color:white; border:0; border-radius:10px; padding:.58rem .75rem; font-weight:800; cursor:pointer; }} button:disabled {{ opacity:.45; cursor:not-allowed; }} .kill-switch {{ background:rgba(255,93,93,.12); color:#ffd8d8; border:1px solid rgba(255,93,93,.48); }} .shutdown-form {{ margin:0; }} .warning,.flash {{ color:#ffe2a9; }} .flash {{ margin:0 0 1rem; padding:.8rem; border:1px solid rgba(245,182,66,.42); border-radius:12px; background:rgba(245,182,66,.09); }} details.command-box {{ margin-top:.75rem; border:1px solid var(--line); border-radius:.65rem; padding:.55rem .7rem; background:rgba(0,0,0,.16); }} details.command-box summary {{ cursor:pointer; color:var(--cyan); font-weight:800; }}
table {{ width:100%; border-collapse:collapse; overflow:hidden; border-radius:12px; }} th,td {{ text-align:left; padding:.75rem .65rem; border-bottom:1px solid var(--line2); vertical-align:top; overflow-wrap:anywhere; }} th {{ color:#c9efff; font-size:.78rem; text-transform:uppercase; letter-spacing:.08em; }} td span {{ color:var(--muted); }}
@media (min-width:1700px) {{ .content-inner {{ max-width:1560px; }} .dashboard-grid {{ grid-template-columns:minmax(430px,.72fr) minmax(760px,1.28fr); }} }}
@media (max-width:1320px) {{ .kpi-strip,.kpis {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .dashboard-grid {{ grid-template-columns:1fr; }} .card-grid {{ grid-template-columns:1fr; }} }}
@media (max-width:900px) {{ :root {{ --sidebar:0px; }} .app-shell {{ grid-template-columns:1fr; }} .sidebar {{ position:relative; width:100%; height:auto; }} .content {{ padding:1rem; }} .kpi-strip,.kpis,.chain,.facts {{ grid-template-columns:1fr; }} .sidebar-footer {{ position:static; margin-top:1rem; }} }}
</style>
</head>
<body>
<div class='app-shell'>
<aside class='sidebar'>
  <div class='logo'><span class='eyebrow'>Sweet Spot — Deep Ocean Intelligence</span><h1>Search Intelligence</h1><p>Control Center</p></div>
  <nav class='side-tabs' >
    {nav_item('dashboard', 'Dashboard', active_tab=active_tab)}
    {nav_item('health', 'Heartbeat & Health', critical_count, active_tab=active_tab)}
    {nav_item('connectors', 'Connectors & Candidates', len(candidates), active_tab=active_tab)}
    {nav_item('approvals', 'Approvals', build_approval_count + registration_approval_count, active_tab=active_tab)}
    {nav_item('gaps', 'Gap Analysis', active_tab=active_tab)}
    {nav_item('jobs', 'Jobs & Applications', active_tab=active_tab)}
    {nav_item('demo-chain', 'Demo Chain', active_tab=active_tab)}
  </nav>
  <div class='sidebar-footer'><span class='mode'>{h(mode)}</span><form class='shutdown-form' method='post' action='/actions/shutdown'><button class='kill-switch' type='submit'>Stop UI</button></form></div>
</aside>
<main class='content'><div class='content-inner'>
  {flash}
  <section class='kpi-strip'>
    {kpi('Active connectors', active_count, 'controlled origin sources', 'ok')}
    {kpi('Build approvals', build_approval_count, 'waiting for your token', 'warn')}
    {kpi('Registration approvals', registration_approval_count, 'after validation', 'neutral')}
    {kpi('Critical FN pressure', critical_count, 'unresolved signals', 'bad')}
  </section>
  {active_view_html}
</div></main>
</div>
</body>
</html>"""
