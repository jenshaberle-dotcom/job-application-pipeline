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
    }
    return special.get(raw, raw.replace("_", " ").replace("-", " ").strip().capitalize())


def risk_class(value: str | None) -> str:
    raw = (value or "").lower()
    if raw in {"critical", "high"}:
        return "bad"
    if raw in {"medium", "manual_review_required"}:
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
        ("Origin exploration", origin_state, humanize(candidate.latest_blocking_gate or "gates reviewed")),
        ("Build", build_state, humanize(candidate.build_status or "not_started")),
        ("Validate", validation_state, humanize(candidate.connector_validation_decision or candidate.connector_validation_status or "open")),
        ("Approval", approval_state, humanize(candidate.final_approval_decision or candidate.final_approval_status or "open")),
        ("Active", active_state, humanize(candidate.status if candidate.is_active_connector else "not_active")),
    )


def render_chain(candidate: ControlCenterCandidate) -> str:
    items = []
    for label, state, title in chain_steps(candidate):
        items.append(f"<li class='{h(state)}' title='{h(title)}'><span></span>{h(label)}</li>")
    return f"<ol class='chain' aria-label='Discovery to controlled activation chain'>{''.join(items)}</ol>"


def render_candidate_row(candidate: ControlCenterCandidate, *, reviewed_by: str, target_location: str, write_actions_enabled: bool) -> str:
    build_form = ""
    if candidate.needs_build_approval:
        cmd = shlex.join(build_approval_command(candidate.company_key, reviewed_by))
        disabled = "disabled" if not write_actions_enabled else ""
        hint = "" if write_actions_enabled else "<p class='warning'>Start the UI with <code>--allow-write-actions</code> to approve builds.</p>"
        build_form = (
            "<div class='action-panel'>"
            "<strong>Build approval</strong>"
            "<p>Allows connector artifacts only. Registration, activation, Bronze writes and scheduler changes stay blocked.</p>"
            "<details class='command-box'><summary>Show approval command</summary>"
            f"<pre>{h(cmd)}</pre>"
            "</details>"
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
    if candidate.needs_registration_approval:
        cmd = shlex.join(registration_approval_command(candidate.company_key, target_location, reviewed_by))
        disabled = "disabled" if not write_actions_enabled else ""
        registration_form = (
            "<div class='action-panel registration'>"
            "<strong>Registration approval</strong>"
            "<p>Approves registration gate only. Controlled activation remains a separate step.</p>"
            "<details class='command-box'><summary>Show registration command</summary>"
            f"<pre>{h(cmd)}</pre>"
            "</details>"
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
    if candidate.connector_module_path or candidate.connector_test_path or candidate.connector_docs_path:
        artifacts = (
            "<ul class='artifacts'>"
            f"<li>{h(candidate.connector_module_path or '-')}</li>"
            f"<li>{h(candidate.connector_test_path or '-')}</li>"
            f"<li>{h(candidate.connector_docs_path or '-')}</li>"
            "</ul>"
        )

    return (
        f"<article class='candidate-card {h(risk_class(candidate.false_negative_risk_level or candidate.status))}'>"
        "<header>"
        f"<div><h3>{h(candidate.company_name)}</h3><p>{h(candidate.company_key)} · {h(candidate.source_name_candidate)}</p></div>"
        f"<span class='pill {h(risk_class(candidate.status))}'>{h(humanize(candidate.status))}</span>"
        "</header>"
        f"{render_chain(candidate)}"
        "<div class='facts'>"
        f"<span>source type: <strong>{h(humanize(candidate.source_type_candidate))}</strong></span>"
        f"<span>candidate risk: <strong>{h(humanize(candidate.operational_risk_level))}</strong></span>"
        f"<span>false-negative risk: <strong>{h(humanize(candidate.false_negative_risk_level or '-'))}</strong></span>"
        f"<span>gates: <strong>{h(candidate.gate_passed_count)}/{h(candidate.gate_total_count)} passed</strong></span>"
        "</div>"
        f"{blocker}"
        f"{artifacts}"
        f"{build_form}"
        f"{registration_form}"
        "</article>"
    )


def render_active_connectors(candidates: Iterable[ControlCenterCandidate]) -> str:
    active = [item for item in candidates if item.is_active_connector]
    if not active:
        return "<section id='active-connectors' class='panel'><h2>Active Connectors</h2><p class='muted'>No active controlled employer-origin connector is registered yet.</p></section>"
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
        "<section id='active-connectors' class='panel'><div class='section-head'><div><span class='eyebrow'>Operational Surface</span>"
        "<h2>Active Connectors</h2></div>"
        f"<span class='pill ok'>{h(len(active))} active</span></div>"
        "<table class='compact-table'><thead><tr><th>Company</th><th>Source</th><th>Type</th><th>Status</th><th>Gates</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></section>"
    )


def render_build_approvals(candidates: Iterable[ControlCenterCandidate], *, reviewed_by: str, target_location: str, write_actions_enabled: bool) -> str:
    items = [item for item in candidates if item.needs_build_approval or item.needs_registration_approval or item.build_status]
    if not items:
        return "<section id='approvals' class='panel'><h2>Connector Approvals</h2><p class='muted'>No connector build or registration approval is waiting.</p></section>"
    cards = [render_candidate_row(item, reviewed_by=reviewed_by, target_location=target_location, write_actions_enabled=write_actions_enabled) for item in items]
    return (
        "<section id='approvals' class='panel approvals'><div class='section-head'><div><span class='eyebrow'>Approval Control</span>"
        "<h2>Connector Build & Registration Approvals</h2></div>"
        f"<span class='pill warn'>{h(len(items))} item(s)</span></div>"
        "<p class='muted'>Build approval may create connector artifacts only. Registration and activation remain separate gates.</p>"
        f"<div class='card-grid'>{''.join(cards)}</div></section>"
    )


def render_candidate_chain(candidates: Iterable[ControlCenterCandidate], *, reviewed_by: str, target_location: str, write_actions_enabled: bool) -> str:
    items = list(candidates)
    if not items:
        return "<section id='candidate-chain' class='panel'><h2>Candidate Chain</h2><p class='muted'>No employer-origin candidates found.</p></section>"
    ordered = sorted(
        items,
        key=lambda item: (
            0 if item.needs_build_approval else 1,
            0 if item.false_negative_risk_level in {"critical", "high"} else 1,
            item.company_name.lower(),
        ),
    )
    cards = [render_candidate_row(item, reviewed_by=reviewed_by, target_location=target_location, write_actions_enabled=write_actions_enabled) for item in ordered]
    return (
        "<section id='candidate-chain' class='panel chain-panel'><div class='section-head'><div><span class='eyebrow'>System Chain</span>"
        "<h2>Discovery → Candidate → Origin Exploration → Connector → Approval</h2></div>"
        f"<span class='pill neutral'>{h(len(items))} candidates</span></div>"
        "<p class='muted'>This is the clean product chain: discovery creates a candidate, Search Intelligence creates pressure, agents explore the origin source, connector artifacts require explicit approval, and registration/activation remain gated.</p>"
        f"<div class='card-grid'>{''.join(cards)}</div></section>"
    )


def render_control_center(
    candidates: list[ControlCenterCandidate],
    *,
    reviewed_by: str,
    target_location: str,
    write_actions_enabled: bool,
    flash_message: str | None = None,
) -> str:
    active_count = sum(1 for item in candidates if item.is_active_connector)
    build_approval_count = sum(1 for item in candidates if item.needs_build_approval)
    registration_approval_count = sum(1 for item in candidates if item.needs_registration_approval)
    critical_count = sum(1 for item in candidates if item.false_negative_risk_level == "critical")
    mode = "write-enabled" if write_actions_enabled else "read-only"
    flash = f"<div class='flash'>{h(flash_message)}</div>" if flash_message else ""
    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Search Intelligence Control Center</title>
<style>
:root {{ color-scheme: dark; --bg:#04101c; --panel:rgba(8,24,39,.94); --panel2:rgba(11,35,56,.78); --line:rgba(99,159,199,.28); --text:#ecf7ff; --muted:#9db8cc; --cyan:#22d3ee; --green:#70e36b; --amber:#f5b642; --red:#ff5d5d; --shadow:0 18px 52px rgba(0,0,0,.34); }}
* {{ box-sizing:border-box; }} body {{ margin:0; font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif; color:var(--text); background:radial-gradient(circle at 20% 0%, rgba(34,211,238,.13), transparent 26%), linear-gradient(135deg, var(--bg), #020712 74%); }}
main {{ width:min(1840px, calc(100vw - 2rem)); max-width:none; margin:0 auto; padding:1.25rem 1rem 2.5rem; }}
.brand {{ display:flex; justify-content:space-between; gap:1rem; align-items:center; border-bottom:1px solid var(--line); padding-bottom:1rem; }}
.brand-actions {{ display:flex; gap:.65rem; align-items:center; flex-wrap:wrap; justify-content:flex-end; }}
.shutdown-form {{ margin:0; }}
.kill-switch {{ background:rgba(255,93,93,.12); color:#ffd8d8; border:1px solid rgba(255,93,93,.48); }}
.kill-switch:hover {{ background:rgba(255,93,93,.22); }}
h1 {{ margin:0; font-size:clamp(1.35rem,2.4vw,2.05rem); letter-spacing:.02em; }} h2,h3 {{ margin:.1rem 0; }} p {{ line-height:1.45; }} .muted {{ color:var(--muted); }} .eyebrow {{ color:var(--cyan); text-transform:uppercase; letter-spacing:.13em; font-size:.72rem; }}
.mode,.pill {{ display:inline-flex; align-items:center; border:1px solid var(--line); border-radius:999px; padding:.34rem .62rem; font-size:.82rem; white-space:nowrap; }} .mode {{ color:var(--cyan); background:rgba(34,211,238,.1); }} .pill.ok {{ color:var(--green); border-color:rgba(112,227,107,.42); }} .pill.warn {{ color:var(--amber); border-color:rgba(245,182,66,.52); }} .pill.bad {{ color:var(--red); border-color:rgba(255,93,93,.50); }} .pill.neutral {{ color:var(--muted); }}
.hero {{ padding:1.2rem 0 .8rem; display:grid; grid-template-columns:1fr auto; gap:1rem; align-items:end; }} .hero p {{ max-width:82ch; }}
.metrics {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.85rem; margin:.75rem 0 1rem; }} .metric,.panel,.candidate-card {{ background:linear-gradient(180deg,var(--panel),rgba(5,16,29,.96)); border:1px solid var(--line); border-radius:16px; box-shadow:var(--shadow); }} .metric {{ padding:.85rem 1rem; }} .metric strong {{ display:block; font-size:1.45rem; }}
.panel {{ padding:1rem; margin:1rem 0; }} .section-head {{ display:flex; justify-content:space-between; gap:1rem; align-items:start; margin-bottom:.75rem; }}
table {{ width:100%; border-collapse:collapse; overflow:hidden; border-radius:12px; }} th,td {{ text-align:left; padding:.7rem .65rem; border-bottom:1px solid var(--line); vertical-align:top; }} th {{ color:#c9efff; font-size:.78rem; text-transform:uppercase; letter-spacing:.08em; }} td span {{ color:var(--muted); }}
.card-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(360px,1fr)); gap:.85rem; }} .candidate-card {{ padding:.9rem; border-left:4px solid var(--line); }} .candidate-card.bad {{ border-left-color:var(--red); }} .candidate-card.warn {{ border-left-color:var(--amber); }} .candidate-card.ok {{ border-left-color:var(--green); }} .candidate-card header {{ display:flex; justify-content:space-between; gap:.75rem; align-items:start; }} .candidate-card header p {{ margin:.15rem 0 0; color:var(--muted); }}
.chain {{ list-style:none; padding:0; margin:.8rem 0; display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.4rem; }} .chain li {{ border:1px solid var(--line); border-radius:999px; padding:.35rem .48rem; font-size:.78rem; color:var(--muted); display:flex; gap:.36rem; align-items:center; }} .chain li span {{ width:.52rem; height:.52rem; border-radius:999px; background:var(--muted); }} .chain li.done {{ color:var(--green); border-color:rgba(112,227,107,.32); }} .chain li.done span {{ background:var(--green); }} .chain li.current {{ color:var(--amber); border-color:rgba(245,182,66,.50); }} .chain li.current span {{ background:var(--amber); }} .chain li.blocked {{ color:var(--red); border-color:rgba(255,93,93,.5); }} .chain li.blocked span {{ background:var(--red); }}
.facts {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.45rem; margin:.65rem 0; }} .facts span {{ color:var(--muted); background:rgba(255,255,255,.025); border:1px solid var(--line); border-radius:10px; padding:.48rem; }} .facts strong {{ color:var(--text); }} .blocker {{ border-left:3px solid var(--amber); padding-left:.65rem; color:#f8ddb0; }} .artifacts {{ margin:.5rem 0; color:var(--muted); }}
.action-panel {{ margin-top:.75rem; padding:.8rem; border:1px solid rgba(245,182,66,.38); border-radius:12px; background:rgba(245,182,66,.08); }} .action-panel.registration {{ border-color:rgba(34,211,238,.42); background:rgba(34,211,238,.08); }} pre {{ white-space:pre-wrap; overflow:auto; padding:.65rem; border-radius:10px; border:1px solid var(--line); background:#03101d; color:#d8f4ff; }} form {{ display:flex; gap:.55rem; flex-wrap:wrap; align-items:end; }} label {{ display:grid; gap:.25rem; color:var(--muted); font-size:.84rem; }} input {{ background:#061522; color:var(--text); border:1px solid var(--line); border-radius:10px; padding:.48rem .58rem; }} button {{ background:linear-gradient(135deg,#13b7d2,#1d78c1); color:white; border:0; border-radius:10px; padding:.58rem .75rem; font-weight:700; cursor:pointer; }} button:disabled {{ opacity:.45; cursor:not-allowed; }} .warning,.flash {{ color:#ffe2a9; }} .flash {{ margin:1rem 0; padding:.8rem; border:1px solid rgba(245,182,66,.42); border-radius:12px; background:rgba(245,182,66,.09); }}
@media (max-width:900px) {{ .metrics,.hero {{ grid-template-columns:1fr; }} .chain,.facts {{ grid-template-columns:1fr; }} .card-grid {{ grid-template-columns:1fr; }} }}

.top-nav {{ position:sticky; top:0; z-index:20; margin:.9rem 0 1rem; padding:.65rem .8rem; display:flex; gap:.6rem; align-items:center; flex-wrap:wrap; background:rgba(3,11,20,.88); backdrop-filter:blur(10px); border:1px solid var(--line); border-radius:1rem; }}
.top-nav a {{ color:var(--text); text-decoration:none; border:1px solid rgba(58,147,191,.45); background:rgba(0,181,255,.06); border-radius:999px; padding:.35rem .65rem; font-size:.78rem; }}
.top-nav a:hover {{ background:rgba(0,181,255,.16); }}
.dashboard-grid {{ display:grid; grid-template-columns:minmax(360px,.82fr) minmax(700px,1.55fr); gap:1rem; align-items:start; }}
@media (max-width:1200px) {{ .dashboard-grid {{ grid-template-columns:1fr; }} }}
.compact-table td, .compact-table th {{ padding:.65rem .5rem; }}
details.command-box {{ margin-top:.75rem; border:1px solid var(--line); border-radius:.65rem; padding:.55rem .7rem; background:rgba(0,0,0,.16); }}
details.command-box summary {{ cursor:pointer; color:var(--cyan); font-weight:700; }}

</style>
</head>
<body><main>
<header class='brand'><div><span class='eyebrow'>Sweet Spot — Deep Ocean Intelligence</span><h1>Search Intelligence Control Center</h1><p class='muted'>From discovered company to approval-gated connector lifecycle.</p></div><div class='brand-actions'><span class='mode'>{h(mode)}</span><form class='shutdown-form' method='post' action='/actions/shutdown'><button class='kill-switch' type='submit' title='Stop local UI server'>Stop UI</button></form></div></header>
<nav class='top-nav'><a href='#overview'>Overview</a><a href='#active-connectors'>Active connectors</a><a href='#approvals'>Approvals</a><a href='#candidate-chain'>Candidate chain</a><a href='/'>Refresh</a></nav>
<section id='overview' class='hero'><div><h2>Operational UI for connector decisions</h2><p class='muted'>Read active connectors, candidates, build approvals and the full discovery-to-approval chain in one surface. Write actions are bounded and require explicit approval tokens.</p></div></section>
{flash}
<section class='metrics'>
<div class='metric'><span class='eyebrow'>Active</span><strong>{h(active_count)}</strong><span class='muted'>controlled connectors</span></div>
<div class='metric'><span class='eyebrow'>Build approvals</span><strong>{h(build_approval_count)}</strong><span class='muted'>waiting for token</span></div>
<div class='metric'><span class='eyebrow'>Registration approvals</span><strong>{h(registration_approval_count)}</strong><span class='muted'>after validation</span></div>
<div class='metric'><span class='eyebrow'>Critical FN risk</span><strong>{h(critical_count)}</strong><span class='muted'>unresolved signals</span></div>
</section>
<div class='dashboard-grid'>
<div>{render_active_connectors(candidates)}</div>
<div>{render_build_approvals(candidates, reviewed_by=reviewed_by, target_location=target_location, write_actions_enabled=write_actions_enabled)}</div>
</div>
{render_candidate_chain(candidates, reviewed_by=reviewed_by, target_location=target_location, write_actions_enabled=write_actions_enabled)}
</main></body></html>"""
