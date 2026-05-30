from __future__ import annotations

import html
import shlex
from dataclasses import dataclass
from typing import Any, Mapping


IMPLEMENTATION_APPROVAL_TOKEN = "approve_connector_implementation"
REGISTRATION_APPROVAL_TOKEN = "approve_connector_registration"
REGISTRATION_PLAN_WRITE_TOKEN = "approve_registration_plan_write"

ACTION_LABELS = {
    "manual_review_stop": "Review required",
    "monitor_source_lifecycle": "Monitoring",
    "run_connector_artifact_generator": "Ready to build",
    "run_connector_validation_agent": "Ready to validate",
    "run_registration_execution_plan_agent": "Registration plan ready",
    "run_connector_build_readiness_agent": "Build readiness check",
    "run_connector_candidate_gate": "Candidate gate check",
    "run_detail_evidence_repair": "Evidence repair available",
    "stop_explicit_approval_required": "Approval required",
    "stop_manual_review_required": "Review required",
}

STATUS_LABELS = {
    "active_controlled": "Active controlled",
    "manual_review_required": "Review required",
    "connector_candidate": "Connector candidate",
    "candidate": "Candidate",
    "blocked": "Blocked",
}

GATE_STATUS_LABELS = {
    "passed": "Passed",
    "manual_review_required": "Needs review",
    "blocked": "Blocked",
    "not_started": "Not started",
}

PHASES = (
    "Discovery",
    "Gates",
    "Build",
    "Validate",
    "Approval",
    "Plan",
    "Monitor",
)


@dataclass(frozen=True)
class WorkspaceActionPlan:
    action: str
    label: str
    token_required: str
    command: tuple[str, ...]
    write_scope: str
    allowed_boundary: str

    @property
    def display_command(self) -> str:
        return shlex.join(self.command)


@dataclass(frozen=True)
class WorkspaceActionDecision:
    allowed: bool
    reason: str
    action_plan: WorkspaceActionPlan | None = None


def build_chain_command(
    *,
    company_key: str,
    target_location: str,
    reviewed_by: str,
    extra_args: tuple[str, ...] = (),
) -> tuple[str, ...]:
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
        *extra_args,
    )


def workspace_action_for_item(
    item: Any,
    *,
    target_location: str,
    reviewed_by: str,
) -> WorkspaceActionPlan | None:
    candidate = item.candidate

    if item.next_action == "run_connector_artifact_generator":
        return WorkspaceActionPlan(
            action="approve_connector_implementation",
            label="Approve connector implementation",
            token_required=IMPLEMENTATION_APPROVAL_TOKEN,
            command=build_chain_command(
                company_key=candidate.company_key,
                target_location=target_location,
                reviewed_by=reviewed_by,
                extra_args=("--write-connector",),
            ),
            write_scope="writes connector candidate artifacts only",
            allowed_boundary="No connector registration, no source activation, no Bronze writes, no scheduler change.",
        )

    if item.next_action == "stop_explicit_approval_required":
        return WorkspaceActionPlan(
            action="approve_connector_registration",
            label="Approve connector registration gate",
            token_required=REGISTRATION_APPROVAL_TOKEN,
            command=build_chain_command(
                company_key=candidate.company_key,
                target_location=target_location,
                reviewed_by=reviewed_by,
                extra_args=("--approval-token", REGISTRATION_APPROVAL_TOKEN),
            ),
            write_scope="writes final_approval_gate only",
            allowed_boundary="No connector activation, no Bronze writes, no scheduler change.",
        )

    if item.next_action == "run_registration_execution_plan_agent":
        return WorkspaceActionPlan(
            action="write_registration_execution_plan",
            label="Write registration execution plan",
            token_required=REGISTRATION_PLAN_WRITE_TOKEN,
            command=build_chain_command(
                company_key=candidate.company_key,
                target_location=target_location,
                reviewed_by=reviewed_by,
                extra_args=("--write-registration-plan",),
            ),
            write_scope="writes a reviewable registration execution plan document only",
            allowed_boundary="No connector activation, no Bronze writes, no scheduler change.",
        )

    return None


def evaluate_workspace_action(
    item: Any,
    *,
    requested_action: str,
    approval_token: str | None,
    write_actions_enabled: bool,
    target_location: str,
    reviewed_by: str,
) -> WorkspaceActionDecision:
    action_plan = workspace_action_for_item(
        item,
        target_location=target_location,
        reviewed_by=reviewed_by,
    )

    if action_plan is None:
        return WorkspaceActionDecision(
            allowed=False,
            reason=f"No UI write action is available for next_action={item.next_action!r}.",
        )

    if requested_action != action_plan.action:
        return WorkspaceActionDecision(
            allowed=False,
            reason=(
                f"Requested action {requested_action!r} does not match the current bounded "
                f"action {action_plan.action!r}."
            ),
            action_plan=action_plan,
        )

    if not write_actions_enabled:
        return WorkspaceActionDecision(
            allowed=False,
            reason="Workspace write actions are disabled. Restart with --allow-write-actions to approve from UI.",
            action_plan=action_plan,
        )

    if approval_token != action_plan.token_required:
        return WorkspaceActionDecision(
            allowed=False,
            reason=f"Exact approval token {action_plan.token_required!r} is required.",
            action_plan=action_plan,
        )

    return WorkspaceActionDecision(
        allowed=True,
        reason="Approved bounded workspace action.",
        action_plan=action_plan,
    )


def display_action(value: str) -> str:
    return ACTION_LABELS.get(value, value.replace("_", " ").title())


def display_status(value: str) -> str:
    return STATUS_LABELS.get(value, value.replace("_", " ").title())


def display_gate_status(value: object) -> str:
    raw = str(value)
    return GATE_STATUS_LABELS.get(raw, raw.replace("_", " ").title())


def h(value: object) -> str:
    return html.escape(str(value), quote=True)


def gate_progress(candidate: Any) -> tuple[int, int, int]:
    total = int(getattr(candidate, "total_gate_count", 0) or 0)
    passed = int(getattr(candidate, "passed_gate_count", 0) or 0)
    percent = round((passed / total) * 100) if total else 0
    return passed, total, percent


def action_family(next_action: str) -> str:
    if next_action in {"run_connector_artifact_generator", "stop_explicit_approval_required", "run_registration_execution_plan_agent"}:
        return "approval"
    if next_action.startswith("run_"):
        return "actionable"
    if next_action.startswith("stop_") or next_action == "manual_review_stop":
        return "review"
    if next_action.startswith("monitor_"):
        return "monitoring"
    return "neutral"


def status_class(value: str) -> str:
    family = action_family(value)
    return {
        "approval": "needs-approval",
        "actionable": "actionable",
        "review": "blocked",
        "monitoring": "monitor",
    }.get(family, "neutral")


def phase_states(item: Any) -> dict[str, str]:
    next_action = item.next_action
    if next_action == "monitor_source_lifecycle":
        return {phase: "complete" for phase in PHASES}

    base = {"Discovery": "complete", "Gates": "complete"}
    if next_action in {"manual_review_stop", "stop_manual_review_required"}:
        return {**base, "Gates": "attention", "Build": "open", "Validate": "open", "Approval": "open", "Plan": "open", "Monitor": "open"}
    if next_action == "run_connector_build_readiness_agent":
        return {**base, "Build": "attention", "Validate": "open", "Approval": "open", "Plan": "open", "Monitor": "open"}
    if next_action == "run_connector_artifact_generator":
        return {**base, "Build": "active", "Validate": "open", "Approval": "open", "Plan": "open", "Monitor": "open"}
    if next_action == "run_connector_validation_agent":
        return {**base, "Build": "complete", "Validate": "active", "Approval": "open", "Plan": "open", "Monitor": "open"}
    if next_action == "stop_explicit_approval_required":
        return {**base, "Build": "complete", "Validate": "complete", "Approval": "attention", "Plan": "open", "Monitor": "open"}
    if next_action == "run_registration_execution_plan_agent":
        return {**base, "Build": "complete", "Validate": "complete", "Approval": "complete", "Plan": "active", "Monitor": "open"}
    return {phase: "open" for phase in PHASES} | {"Discovery": "active"}


def render_phase_tracker(item: Any) -> str:
    states = phase_states(item)
    parts = []
    for phase in PHASES:
        state = states.get(phase, "open")
        parts.append(f"<span class='phase {h(state)}' title='{h(state)}'>{h(phase)}</span>")
    return "<div class='phase-tracker' aria-label='Connector lifecycle phases'>" + "".join(parts) + "</div>"


def render_progress(candidate: Any) -> str:
    passed, total, percent = gate_progress(candidate)
    manual = int(getattr(candidate, "manual_review_gate_count", 0) or 0)
    blocked = int(getattr(candidate, "blocked_gate_count", 0) or 0)
    remaining = max(total - passed - manual - blocked, 0)
    return (
        "<div class='progress-block'>"
        "<div class='progress-row'>"
        f"<strong>{passed} of {total} gates passed</strong>"
        f"<span>{percent}%</span>"
        "</div>"
        f"<div class='progress' aria-label='{h(percent)} percent complete'><span style='width: {h(percent)}%'></span></div>"
        "<div class='gate-chips'>"
        f"<span class='chip ok'>{passed} passed</span>"
        f"<span class='chip warn'>{manual} need review</span>"
        f"<span class='chip bad'>{blocked} blocked</span>"
        f"<span class='chip neutral'>{remaining} open</span>"
        "</div>"
        "</div>"
    )


def render_review_panel(item: Any) -> str:
    if item.next_action == "manual_review_stop" or item.next_action.startswith("stop_"):
        return (
            "<div class='review-panel'>"
            "<strong>Review required</strong>"
            "<p>This candidate is intentionally paused. The workspace does not offer an approval button "
            "because the current gate state is not implementable by approval alone.</p>"
            f"<p><strong>Current blocker:</strong> {h(item.reason)}</p>"
            "<p class='muted'>Next human step: inspect gate details, collect new evidence, or leave the candidate parked. "
            "A future workspace iteration should turn this into a dedicated recheck/defer action.</p>"
            "</div>"
        )

    return "<p class='muted'>No bounded UI action available for this candidate.</p>"


def render_gate_table(gates: Mapping[str, object]) -> str:
    if not gates:
        return "<p class='muted'>No gate reviews recorded yet.</p>"

    rows: list[str] = []
    for gate_name in sorted(gates):
        gate = gates[gate_name]
        rows.append(
            "<tr>"
            f"<td>{h(getattr(gate, 'gate_name', gate_name))}</td>"
            f"<td title='{h(getattr(gate, 'gate_status', '-'))}'>{h(display_gate_status(getattr(gate, 'gate_status', '-')))}</td>"
            f"<td>{h(getattr(gate, 'decision', '-'))}</td>"
            f"<td>{h(getattr(gate, 'stop_reason', '') or '')}</td>"
            "</tr>"
        )

    return (
        "<table class='gates'>"
        "<thead><tr><th>Gate</th><th>Status</th><th>Decision</th><th>Stop reason</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def render_action_panel(
    item: Any,
    *,
    target_location: str,
    reviewed_by: str,
    write_actions_enabled: bool,
) -> str:
    action_plan = workspace_action_for_item(
        item,
        target_location=target_location,
        reviewed_by=reviewed_by,
    )
    if action_plan is None:
        if item.next_action == "manual_review_stop" or item.next_action.startswith("stop_"):
            return render_review_panel(item)
        if item.command:
            return (
                "<div class='command-panel'>"
                "<strong>Next console command</strong>"
                f"<pre>{h(item.command)}</pre>"
                "</div>"
            )
        return render_review_panel(item)

    disabled_hint = "" if write_actions_enabled else "<p class='warning'>UI write actions disabled. Start with <code>--allow-write-actions</code> to enable this button.</p>"
    return (
        "<div class='approval-panel'>"
        f"<strong>{h(action_plan.label)}</strong>"
        f"<p>{h(action_plan.write_scope)}. {h(action_plan.allowed_boundary)}</p>"
        f"<pre>{h(action_plan.display_command)}</pre>"
        f"{disabled_hint}"
        "<form method='post' action='/actions/run'>"
        f"<input type='hidden' name='company_key' value='{h(item.candidate.company_key)}'>"
        f"<input type='hidden' name='requested_action' value='{h(action_plan.action)}'>"
        "<label>Approval token "
        f"<input name='approval_token' placeholder='{h(action_plan.token_required)}' autocomplete='off'></label>"
        "<label>Reviewed by <input name='reviewed_by' value='jens'></label>"
        f"<button type='submit' {'disabled' if not write_actions_enabled else ''}>{h(action_plan.label)}</button>"
        "</form>"
        "</div>"
    )


def render_candidate_card(
    item: Any,
    *,
    gate_table: str,
    action_panel: str,
) -> str:
    candidate = item.candidate
    css_class = status_class(item.next_action)
    return (
        f"<article class='candidate-card {css_class}'>"
        "<header class='candidate-head'>"
        "<div>"
        f"<h3>{h(candidate.company_name)}</h3>"
        f"<p class='muted'>{h(candidate.company_key)} · {h(candidate.source_name_candidate)}</p>"
        "</div>"
        f"<span class='badge' title='{h(item.next_action)}'>{h(display_action(item.next_action))}</span>"
        "</header>"
        "<section class='candidate-grid'>"
        f"<p><span class='field-label'>Status</span><br><span title='{h(candidate.status)}'>{h(display_status(candidate.status))}</span></p>"
        f"<p><span class='field-label'>Risk</span><br>{h(candidate.risk_level)}</p>"
        f"<div><span class='field-label'>Gate progress</span>{render_progress(candidate)}</div>"
        "</section>"
        f"{render_phase_tracker(item)}"
        f"<p class='reason'><strong>Why this state?</strong> {h(item.reason)}</p>"
        f"{action_panel}"
        "<details><summary>Gate details</summary>"
        f"{gate_table}"
        "</details>"
        "</article>"
    )


def render_workspace_html(
    queue_items: list[Any],
    gates_by_candidate_id: Mapping[int, Mapping[str, object]],
    *,
    target_location: str,
    reviewed_by: str,
    write_actions_enabled: bool,
    flash_message: str | None = None,
) -> str:
    needs_approval = sum(1 for item in queue_items if workspace_action_for_item(item, target_location=target_location, reviewed_by=reviewed_by))
    actionable = sum(1 for item in queue_items if item.command)
    blocked = sum(1 for item in queue_items if item.next_action.startswith("stop_") or item.next_action == "manual_review_stop")
    monitoring = sum(1 for item in queue_items if item.next_action == "monitor_source_lifecycle")

    cards: list[str] = []
    for item in queue_items:
        candidate = item.candidate
        gate_table = render_gate_table(gates_by_candidate_id.get(candidate.candidate_id, {}))
        action_panel = render_action_panel(
            item,
            target_location=target_location,
            reviewed_by=reviewed_by,
            write_actions_enabled=write_actions_enabled,
        )
        cards.append(render_candidate_card(item, gate_table=gate_table, action_panel=action_panel))

    flash = f"<div class='flash'>{h(flash_message)}</div>" if flash_message else ""
    mode = "write-enabled" if write_actions_enabled else "read-only"
    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Job-Pipeline Approval Workspace</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #06111f;
  --bg-2: #081827;
  --panel: rgba(8, 24, 39, .92);
  --panel-soft: rgba(10, 31, 50, .72);
  --line: #1e3a55;
  --line-strong: #2b5d82;
  --text: #e8f3ff;
  --muted: #94b6d5;
  --cyan: #22d3ee;
  --cyan-soft: rgba(34, 211, 238, .12);
  --green: #70e060;
  --green-soft: rgba(112, 224, 96, .12);
  --amber: #f6b62d;
  --amber-soft: rgba(246, 182, 45, .12);
  --red: #ff5b61;
  --red-soft: rgba(255, 91, 97, .10);
  --shadow: 0 20px 60px rgba(0, 0, 0, .34);
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
  background:
    radial-gradient(circle at 18% 0%, rgba(34, 211, 238, .14), transparent 30%),
    linear-gradient(135deg, #040a14 0%, var(--bg) 44%, #071a2b 100%);
  color: var(--text);
}}
main {{ max-width: 1220px; margin: 0 auto; padding: 1.25rem 1.5rem 2rem; }}
.brandbar {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border-bottom: 1px solid var(--line);
  padding-bottom: 1rem;
  margin-bottom: 1rem;
}}
.brand-title {{ display: flex; align-items: center; gap: .85rem; }}
.logo {{
  width: 42px; height: 42px; border: 2px solid var(--cyan); border-radius: 13px;
  display: grid; place-items: center; color: var(--cyan); font-weight: 800;
  box-shadow: 0 0 26px rgba(34, 211, 238, .16);
}}
h1 {{ margin: 0; font-size: clamp(1.6rem, 3vw, 2.25rem); letter-spacing: -.04em; }}
.eyebrow {{ margin: .1rem 0 0; color: var(--cyan); font-size: .85rem; font-weight: 700; letter-spacing: .02em; }}
.mode-pill {{ border: 1px solid var(--line-strong); border-radius: 999px; padding: .45rem .7rem; color: var(--muted); background: rgba(3, 12, 23, .52); }}
.top-actions {{ display: flex; gap: .6rem; align-items: center; flex-wrap: wrap; justify-content: flex-end; }}
.boundary {{ color: var(--muted); max-width: 900px; margin: 0 0 1.15rem; line-height: 1.45; }}
.summary {{ display: grid; grid-template-columns: repeat(4, minmax(170px, 1fr)); gap: .85rem; margin: 1rem 0; }}
.metric, .candidate-card, .workspace-note {{
  background: linear-gradient(180deg, rgba(11, 31, 51, .92), rgba(7, 20, 35, .92));
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: var(--shadow);
}}
.metric {{ padding: .85rem 1rem; min-height: 92px; }}
.metric span:first-child {{ color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .08em; }}
.metric strong {{ display: block; margin-top: .55rem; font-size: 1.55rem; }}
.metric .metric-sub {{ color: var(--muted); font-size: .82rem; margin-top: .15rem; }}
.section-head {{ display: flex; justify-content: space-between; gap: 1rem; align-items: end; margin: 1.3rem 0 .7rem; }}
.section-head h2 {{ margin: 0; font-size: 1.1rem; text-transform: uppercase; letter-spacing: .08em; color: #bdefff; }}
.workspace-note {{ padding: .8rem 1rem; color: var(--muted); }}
.candidate-list {{ display: grid; gap: .85rem; }}
.candidate-card {{ padding: .9rem; }}
.candidate-head {{ display: flex; justify-content: space-between; gap: .85rem; align-items: flex-start; }}
.candidate-card h3 {{ margin: 0; font-size: 1.15rem; letter-spacing: -.02em; }}
.muted {{ color: var(--muted); }}
.badge {{ border: 1px solid var(--line-strong); border-radius: 999px; padding: .32rem .62rem; font-size: .78rem; white-space: nowrap; background: rgba(4, 12, 23, .42); }}
.needs-approval .badge {{ border-color: var(--amber); color: var(--amber); }}
.blocked .badge {{ border-color: var(--red); color: var(--red); }}
.actionable .badge {{ border-color: var(--cyan); color: var(--cyan); }}
.monitor .badge {{ border-color: var(--green); color: var(--green); }}
.candidate-grid {{ display: grid; grid-template-columns: 1.2fr .8fr 1.7fr; gap: 1rem; align-items: start; margin-top: .75rem; }}
.field-label {{ color: #bdefff; font-weight: 800; font-size: .76rem; text-transform: uppercase; letter-spacing: .06em; }}
.reason {{ margin: .75rem 0 .6rem; line-height: 1.35; }}
.progress-block {{ margin-top: .3rem; }}
.progress-row {{ display: flex; justify-content: space-between; gap: 1rem; margin-bottom: .35rem; font-size: .9rem; }}
.progress {{ height: .55rem; background: #04101e; border: 1px solid var(--line); border-radius: 999px; overflow: hidden; }}
.progress span {{ display: block; height: 100%; background: linear-gradient(90deg, #48ddff, #7dd3fc); }}
.gate-chips {{ display: flex; flex-wrap: wrap; gap: .35rem; margin-top: .5rem; }}
.chip {{ border: 1px solid var(--line); border-radius: 999px; padding: .18rem .5rem; font-size: .74rem; background: rgba(4, 12, 23, .44); }}
.chip.ok {{ border-color: var(--green); color: var(--green); }}
.chip.warn {{ border-color: var(--amber); color: var(--amber); }}
.chip.bad {{ border-color: var(--red); color: var(--red); }}
.phase-tracker {{ display: grid; grid-template-columns: repeat(7, minmax(82px, 1fr)); gap: .35rem; margin: .8rem 0; }}
.phase {{
  border: 1px solid var(--line); border-radius: 999px; padding: .3rem .4rem; text-align: center;
  color: var(--muted); font-size: .74rem; background: rgba(2, 10, 18, .46);
}}
.phase.complete {{ border-color: rgba(112, 224, 96, .7); color: var(--green); background: var(--green-soft); }}
.phase.active {{ border-color: var(--cyan); color: var(--cyan); background: var(--cyan-soft); }}
.phase.attention {{ border-color: var(--amber); color: var(--amber); background: var(--amber-soft); }}
.approval-panel, .command-panel, .review-panel, .flash {{ border: 1px solid var(--line); border-radius: 14px; padding: .85rem; margin: .75rem 0; background: rgba(3, 12, 23, .36); }}
.review-panel {{ border-color: var(--amber); background: var(--amber-soft); }}
.flash {{ border-color: var(--cyan); color: #c9f7ff; }}
.warning {{ color: var(--amber); }}
pre {{ overflow: auto; background: #020812; padding: .75rem; border-radius: 12px; border: 1px solid var(--line); }}
form {{ display: flex; flex-wrap: wrap; gap: .7rem; align-items: end; }}
input {{ padding: .55rem; border-radius: 10px; border: 1px solid var(--line); min-width: 230px; background: #06111f; color: var(--text); }}
button {{ padding: .65rem .9rem; border-radius: 12px; border: 0; font-weight: 800; cursor: pointer; background: var(--cyan); color: #03111c; }}
button.secondary {{ background: transparent; border: 1px solid var(--line-strong); color: var(--text); }}
button:disabled {{ opacity: .45; cursor: not-allowed; }}
details {{ margin-top: .45rem; }}
summary {{ cursor: pointer; color: #c7edff; }}
table {{ width: 100%; border-collapse: collapse; margin-top: .75rem; }}
th, td {{ text-align: left; border-bottom: 1px solid var(--line); padding: .45rem; vertical-align: top; }}
.footer-note {{ margin-top: 1.4rem; padding: .8rem 1rem; border: 1px solid var(--line); border-radius: 14px; color: var(--muted); display: flex; justify-content: space-between; gap: 1rem; }}
@media (max-width: 900px) {{
  main {{ padding: 1rem; }}
  .brandbar, .section-head, .candidate-head, .footer-note {{ flex-direction: column; align-items: flex-start; }}
  .summary {{ grid-template-columns: repeat(2, minmax(140px, 1fr)); }}
  .candidate-grid {{ grid-template-columns: 1fr; }}
  .phase-tracker {{ grid-template-columns: repeat(2, minmax(110px, 1fr)); }}
}}
</style>
</head>
<body>
<main>
<header class='brandbar'>
  <div class='brand-title'>
    <div class='logo'>JP</div>
    <div>
      <h1>Job-Pipeline Approval Workspace</h1>
      <p class='eyebrow'>Employer-Origin Agents · Sweet Spot — Balanced Intelligence</p>
    </div>
  </div>
  <div class='top-actions'>
    <span class='mode-pill'>Mode: <strong>{h(mode)}</strong></span>
    <form method='post' action='/actions/shutdown'><button class='secondary' type='submit'>Stop workspace</button></form>
  </div>
</header>
<p class='boundary'>Approval surface for DB-backed connector agents. It never activates sources, writes Bronze rows, registers schedulers or uses CSV/export files as pipeline inputs.</p>
{flash}
<section class='summary' aria-label='Workspace summary'>
  <div class='metric'><span>Candidates</span><strong>{len(queue_items)}</strong><div class='metric-sub'>Employer-origin queue</div></div>
  <div class='metric'><span>Approval actions</span><strong>{needs_approval}</strong><div class='metric-sub'>Require explicit token</div></div>
  <div class='metric'><span>Review stops</span><strong>{blocked}</strong><div class='metric-sub'>Need human decision</div></div>
  <div class='metric'><span>Monitoring</span><strong>{monitoring}</strong><div class='metric-sub'>Active controlled sources</div></div>
</section>
<div class='section-head'>
  <div>
    <h2>Candidate Landscape</h2>
    <p class='muted'>Compact cards first; gate evidence stays collapsed until you actively review a candidate.</p>
  </div>
  <p class='muted'>{actionable} actionable console commands · target location: {h(target_location)}</p>
</div>
<section class='candidate-list'>
{''.join(cards)}
</section>
<div class='footer-note'>
  <span>Intelligence by design: better decisions through transparent gates, not more blind automation.</span>
  <span>Reviewed by: {h(reviewed_by)}</span>
</div>
</main>
</body>
</html>"""
