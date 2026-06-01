from __future__ import annotations

import html
import shlex
from urllib.parse import urlencode
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
    "not_started": "Open",
}

PIPELINE_PHASES = (
    "Discovery",
    "Gates",
    "Build",
    "Validate",
    "Approval",
    "Plan",
    "Monitor",
)

WORKSPACE_VIEWS = (
    ("all", "All"),
    ("review_required", "Review required"),
    ("approval_required", "Approval required"),
    ("ready", "Ready / next step"),
    ("false_negative", "False negative risk"),
    ("reassessment", "Reassessment"),
    ("learning", "Learning"),
    ("vocabulary", "Vocabulary"),
    ("strategy", "Strategy"),
    ("trials", "Trials"),
    ("active", "Active"),
)

VIEW_ALIASES = {key for key, _label in WORKSPACE_VIEWS}


@dataclass(frozen=True)
class WorkspaceCompanyVocabulary:
    company_key: str
    company_name: str | None
    observed_term: str
    source_name: str
    observation_count: int
    last_seen_at: str | None


@dataclass(frozen=True)
class WorkspaceFalseNegativeRisk:
    candidate_id: int
    company_key: str
    company_name: str
    risk_level: str
    sighting_count: int
    recent_sighting_count: int
    last_observed_at: str | None
    suggested_search_terms: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class WorkspaceReassessmentItem:
    queue_id: int
    candidate_id: int
    company_key: str
    company_name: str
    risk_level: str
    priority: int
    trigger_reason: str
    suggested_search_terms: tuple[str, ...]
    status: str
    updated_at: str | None



@dataclass(frozen=True)
class WorkspaceSearchStrategyRecommendation:
    recommendation_id: int
    company_key: str
    source_family_candidate: str | None
    suggested_term: str
    recommendation_type: str
    recommendation_status: str
    autonomy_level: str
    confidence_score: str
    confidence_level: str
    sample_size: int
    false_negative_risk_level: str | None
    false_negative_sighting_count: int
    guardrail_decision: str
    reason: str
    updated_at: str | None


@dataclass(frozen=True)
class WorkspaceTrialTerm:
    trial_id: int
    company_key: str
    source_family_candidate: str | None
    suggested_term: str
    trial_status: str
    autonomy_level: str
    guardrail_decision: str
    trial_expires_at: str | None
    max_result_volume: int
    max_noise_rate: str
    applied_by: str
    updated_at: str | None


@dataclass(frozen=True)
class WorkspaceSearchTermConfidence:
    suggested_term: str
    source_family_candidate: str | None
    sample_size: int
    success_count: int
    failure_count: int
    noise_count: int
    confidence_score: str
    confidence_level: str
    created_at: str | None


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
            write_scope="Writes connector candidate artifacts only",
            allowed_boundary="No connector registration, source activation, Bronze writes or scheduler change.",
        )

    if item.next_action == "stop_explicit_approval_required":
        return WorkspaceActionPlan(
            action="approve_connector_registration",
            label="Approve registration gate",
            token_required=REGISTRATION_APPROVAL_TOKEN,
            command=build_chain_command(
                company_key=candidate.company_key,
                target_location=target_location,
                reviewed_by=reviewed_by,
                extra_args=("--approval-token", REGISTRATION_APPROVAL_TOKEN),
            ),
            write_scope="Writes final_approval_gate only",
            allowed_boundary="No connector activation, Bronze writes or scheduler change.",
        )

    if item.next_action == "run_registration_execution_plan_agent":
        return WorkspaceActionPlan(
            action="write_registration_execution_plan",
            label="Write registration plan",
            token_required=REGISTRATION_PLAN_WRITE_TOKEN,
            command=build_chain_command(
                company_key=candidate.company_key,
                target_location=target_location,
                reviewed_by=reviewed_by,
                extra_args=("--write-registration-plan",),
            ),
            write_scope="Writes a reviewable registration execution plan document only",
            allowed_boundary="No connector activation, Bronze writes or scheduler change.",
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


def gate_counts(candidate: Any) -> tuple[int, int, int, int, int]:
    total = int(getattr(candidate, "total_gate_count", 0) or 0)
    passed = int(getattr(candidate, "passed_gate_count", 0) or 0)
    manual = int(getattr(candidate, "manual_review_gate_count", 0) or 0)
    blocked = int(getattr(candidate, "blocked_gate_count", 0) or 0)
    open_count = max(total - passed - manual - blocked, 0)
    return passed, manual, blocked, open_count, total


def gate_percent(candidate: Any) -> int:
    passed, _manual, _blocked, _open_count, total = gate_counts(candidate)
    return round((passed / total) * 100) if total else 0


def phase_index(item: Any) -> int:
    if item.next_action.startswith("monitor_") or item.candidate.status == "active_controlled":
        return 6
    if item.next_action == "run_registration_execution_plan_agent":
        return 5
    if item.next_action == "stop_explicit_approval_required":
        return 4
    if item.next_action == "run_connector_validation_agent":
        return 3
    if item.next_action == "run_connector_artifact_generator":
        return 2
    if "gate" in item.next_action or item.next_action in {"manual_review_stop", "stop_manual_review_required"}:
        return 1
    return 0


def render_phase_tracker(item: Any) -> str:
    current = phase_index(item)
    steps = []
    for index, label in enumerate(PIPELINE_PHASES):
        if index < current:
            css = "done"
        elif index == current:
            css = "current"
        else:
            css = "open"
        steps.append(f"<li class='{css}'><span></span>{h(label)}</li>")
    return f"<ol class='phase-tracker' aria-label='Connector lifecycle phase'>{''.join(steps)}</ol>"


def render_progress(candidate: Any) -> str:
    passed, manual, blocked, open_count, total = gate_counts(candidate)
    percent = gate_percent(candidate)
    return (
        "<div class='progress-block'>"
        "<div class='progress-row'>"
        f"<strong>{passed} of {total} gates passed</strong>"
        f"<span>{percent}%</span>"
        "</div>"
        f"<div class='progress' aria-label='{h(percent)} percent complete'><span style='width: {h(percent)}%'></span></div>"
        "<div class='gate-chips' aria-label='Gate state summary'>"
        f"<span class='chip ok'>{passed} passed</span>"
        f"<span class='chip warn'>{manual} review</span>"
        f"<span class='chip bad'>{blocked} blocked</span>"
        f"<span class='chip neutral'>{open_count} open</span>"
        "</div>"
        "</div>"
    )


def render_review_panel(item: Any) -> str:
    if item.next_action == "manual_review_stop" or item.next_action.startswith("stop_"):
        return (
            "<div class='review-panel'>"
            "<strong>Review required</strong>"
            "<p>This candidate is paused because the current gates are not implementable by approval alone.</p>"
            f"<p><strong>Current blocker:</strong> {h(item.reason)}</p>"
            "<p class='muted'>Next human step: inspect the details, collect new evidence, or leave the candidate parked. "
            "A later workspace iteration should add explicit recheck/defer decisions here.</p>"
            "</div>"
        )

    return "<p class='muted'>No bounded UI action available for this candidate.</p>"


def status_class(value: str) -> str:
    if value in {"run_connector_artifact_generator", "stop_explicit_approval_required"}:
        return "needs-approval"
    if value.startswith("run_"):
        return "actionable"
    if value.startswith("stop_") or value == "manual_review_stop":
        return "blocked"
    if value.startswith("monitor_"):
        return "monitor"
    return "neutral"


def normalize_view(value: str | None) -> str:
    return value if value in VIEW_ALIASES else "all"


def workspace_view_for_item(item: Any) -> str:
    if item.next_action.startswith("monitor_") or item.candidate.status == "active_controlled":
        return "active"
    if item.next_action in {
        "run_connector_artifact_generator",
        "stop_explicit_approval_required",
        "run_registration_execution_plan_agent",
    }:
        return "approval_required"
    if item.next_action.startswith("stop_") or item.next_action == "manual_review_stop":
        return "review_required"
    if item.next_action.startswith("run_") or item.command:
        return "ready"
    return "review_required"


def workspace_view_counts(queue_items: list[Any]) -> dict[str, int]:
    counts = {key: 0 for key, _label in WORKSPACE_VIEWS}
    counts["all"] = len(queue_items)
    for item in queue_items:
        counts[workspace_view_for_item(item)] = counts.get(workspace_view_for_item(item), 0) + 1
    return counts


def item_matches_search(item: Any, search_query: str) -> bool:
    query = search_query.strip().lower()
    if not query:
        return True

    candidate = item.candidate
    haystack = " ".join(
        str(value).lower()
        for value in (
            candidate.company_key,
            candidate.company_name,
            candidate.source_name_candidate,
            candidate.source_family_candidate,
            candidate.status,
            candidate.risk_level,
            item.next_action,
            item.reason,
        )
    )
    return query in haystack


def filter_workspace_items(
    queue_items: list[Any],
    *,
    selected_view: str = "all",
    search_query: str = "",
) -> list[Any]:
    view = normalize_view(selected_view)
    return [
        item
        for item in queue_items
        if (view == "all" or workspace_view_for_item(item) == view)
        and item_matches_search(item, search_query)
    ]


def workspace_url(*, selected_view: str, search_query: str) -> str:
    params: dict[str, str] = {}
    if normalize_view(selected_view) != "all":
        params["view"] = normalize_view(selected_view)
    if search_query.strip():
        params["q"] = search_query.strip()
    query = urlencode(params)
    return f"/?{query}" if query else "/"


def render_view_controls(
    *,
    selected_view: str,
    search_query: str,
    counts: Mapping[str, int],
    visible_count: int,
    total_count: int,
) -> str:
    selected = normalize_view(selected_view)
    tabs = []
    for key, label in WORKSPACE_VIEWS:
        css = "active" if key == selected else ""
        tabs.append(
            f"<a class='view-tab {css}' href='{h(workspace_url(selected_view=key, search_query=search_query))}'>"
            f"<span>{h(label)}</span><strong>{h(counts.get(key, 0))}</strong></a>"
        )

    clear_link = ""
    if selected != "all" or search_query.strip():
        clear_link = "<a class='clear-filter' href='/'>Clear filters</a>"

    return (
        "<section class='workspace-controls' aria-label='Candidate filters'>"
        f"<nav class='view-tabs' aria-label='Candidate status filters'>{''.join(tabs)}</nav>"
        "<form method='get' action='/' class='search-form'>"
        f"<input type='hidden' name='view' value='{h(selected)}'>"
        f"<label>Search candidates <input name='q' value='{h(search_query)}' placeholder='company, status, next action'></label>"
        "<button type='submit'>Search</button>"
        f"{clear_link}"
        "</form>"
        f"<p class='result-count'>Showing {h(visible_count)} of {h(total_count)} candidates.</p>"
        "</section>"
    )


def render_empty_state(*, selected_view: str, search_query: str) -> str:
    parts = []
    if normalize_view(selected_view) != "all":
        parts.append(f"view '{normalize_view(selected_view).replace('_', ' ')}'")
    if search_query.strip():
        parts.append(f"search '{search_query.strip()}'")
    suffix = " for " + " and ".join(parts) if parts else ""
    return (
        "<section class='empty-state'>"
        f"<strong>No candidates{h(suffix)}.</strong>"
        "<p>Adjust filters or clear the search to return to the full candidate landscape.</p>"
        "</section>"
    )


def render_gate_table(gates: Mapping[str, object]) -> str:
    if not gates:
        return "<p class='muted'>No gate reviews recorded yet.</p>"

    rows: list[str] = []
    for gate_name in sorted(gates):
        gate = gates[gate_name]
        rows.append(
            "<tr>"
            f"<td><code title='{h(getattr(gate, 'gate_name', gate_name))}'>{h(humanize_identifier(getattr(gate, 'gate_name', gate_name)))}</code></td>"
            f"<td title='{h(display_gate_status(getattr(gate, 'gate_status', '-')))}'>{h(display_gate_status(getattr(gate, 'gate_status', '-')))}</td>"
            f"<td><code title='{h(humanize_state(getattr(gate, 'decision', '-')))}'>{h(humanize_state(getattr(gate, 'decision', '-')))}</code></td>"
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

    disabled_hint = "" if write_actions_enabled else "<p class='warning'>Start with <code>--allow-write-actions</code> to enable this approval action.</p>"
    return (
        "<div class='approval-panel'>"
        f"<strong>{h(action_plan.label)}</strong>"
        f"<p>{h(action_plan.write_scope)}. {h(action_plan.allowed_boundary)}</p>"
        f"<pre>{h(action_plan.display_command)}</pre>"
        f"{disabled_hint}"
        "<form method='post' action='/actions/run' class='approval-form'>"
        f"<input type='hidden' name='company_key' value='{h(item.candidate.company_key)}'>"
        f"<input type='hidden' name='requested_action' value='{h(action_plan.action)}'>"
        "<label>Approval token "
        f"<input name='approval_token' placeholder='{h(action_plan.token_required)}' autocomplete='off'></label>"
        f"<label>Reviewed by <input name='reviewed_by' value='{h(reviewed_by)}'></label>"
        f"<button type='submit' {'disabled' if not write_actions_enabled else ''}>{h(action_plan.label)}</button>"
        "</form>"
        "</div>"
    )


def render_candidate_card(
    item: Any,
    gates: Mapping[str, object],
    *,
    target_location: str,
    reviewed_by: str,
    write_actions_enabled: bool,
) -> str:
    candidate = item.candidate
    css_class = status_class(item.next_action)
    gate_table = render_gate_table(gates)
    action_panel = render_action_panel(
        item,
        target_location=target_location,
        reviewed_by=reviewed_by,
        write_actions_enabled=write_actions_enabled,
    )
    percent = gate_percent(candidate)
    return (
        f"<article class='candidate-card {css_class}'>"
        "<div class='candidate-main'>"
        "<header class='candidate-header'>"
        "<div>"
        f"<h2>{h(candidate.company_name)}</h2>"
        f"<p class='muted'>{h(candidate.company_key)} · {h(candidate.source_name_candidate)}</p>"
        "</div>"
        f"<span class='status-pill' title='{h(item.next_action)}'>{h(display_action(item.next_action))}</span>"
        "</header>"
        "<div class='candidate-grid'>"
        f"<p><span class='label'>Status</span><strong title='{h(candidate.status)}'>{h(display_status(candidate.status))}</strong></p>"
        f"<p><span class='label'>Risk</span><strong>{h(candidate.risk_level.title())}</strong></p>"
        f"<p><span class='label'>Progress</span><strong>{percent}% complete</strong></p>"
        "</div>"
        f"{render_progress(candidate)}"
        f"{render_phase_tracker(item)}"
        f"<p class='reason'><strong>Reason:</strong> {h(item.reason)}</p>"
        f"{action_panel}"
        "<details class='gate-details'><summary>Gate details</summary>"
        f"{gate_table}"
        "</details>"
        "</div>"
        "</article>"
    )


def risk_badge_class(risk_level: str) -> str:
    if risk_level in {"critical", "high"}:
        return "bad"
    if risk_level == "medium":
        return "warn"
    return "ok"



def humanize_timestamp(value: object) -> str:
    if value is None:
        return "-"
    raw = str(value)
    if not raw:
        return "-"
    if raw.startswith("2026-05-31"):
        return "today"
    if " " in raw:
        return raw.split(" ", 1)[0]
    if "T" in raw:
        return raw.split("T", 1)[0]
    return raw


def humanize_identifier(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "-"
    special = {
        "company_candidate": "Company candidate",
        "source_discovery": "Source discovery",
        "risk_gate": "Risk",
        "technical_reachability_gate": "Technical reachability",
        "scope_gate": "Scope",
        "defensive_preview_gate": "Defensive preview",
        "relevance_gate": "Relevance",
        "detail_evidence_gate": "Detail evidence",
        "incremental_uniqueness_gate": "Incremental uniqueness",
        "connector_candidate_gate": "Connector candidate",
        "controlled_activation_gate": "Controlled activation",
        "bronze_validation": "Bronze validation",
        "silver_validation": "Silver validation",
        "source_lifecycle_tracking": "Source lifecycle",
    }
    if raw in special:
        return special[raw]
    return raw.replace("_", " ").replace("-", " ").strip().capitalize()


def humanize_state(value: object) -> str:
    raw = str(value or "").strip()
    special = {
        "manual_review_required": "Needs review",
        "not_started": "Open",
        "passed": "Passed",
        "blocked": "Blocked",
        "continue": "Continue",
        "defer": "Deferred",
        "build_connector_candidate": "Build candidate",
        "ready_for_final_approval": "Ready for approval",
    }
    if raw in special:
        return special[raw]
    return humanize_identifier(raw)


def render_company_vocabulary_section(
    vocabulary_items: list[WorkspaceCompanyVocabulary] | None,
) -> str:
    items = vocabulary_items or []
    if not items:
        return ""

    by_company: dict[str, list[WorkspaceCompanyVocabulary]] = {}
    for item in items:
        by_company.setdefault(item.company_key, []).append(item)

    rows: list[str] = []
    for company_key, company_items in list(by_company.items())[:8]:
        company_name = next((item.company_name for item in company_items if item.company_name), company_key)
        top_terms = ", ".join(
            f"{item.observed_term} ({item.observation_count})"
            for item in sorted(company_items, key=lambda x: (-x.observation_count, x.observed_term))[:6]
        )
        sources = ", ".join(sorted({item.source_name for item in company_items})[:3])
        rows.append(
            "<article class='risk-row'>"
            "<div>"
            f"<strong>{h(company_name)}</strong>"
            f"<p class='muted'>{h(company_key)} · sources: {h(sources or '-')}</p>"
            "</div>"
            "<div class='risk-row-facts'>"
            f"<span>terms: {h(top_terms or '-')}</span>"
            "</div>"
            "</article>"
        )

    return (
        "<section class='risk-section compact-risk panel'>"
        "<div class='section-heading'>"
        "<div><span class='eyebrow'>Search Intelligence</span>"
        "<h3>Company Vocabulary</h3></div>"
        f"<span class='status-pill read'>{h(len(by_company))} companies</span>"
        "</div>"
        "<p class='muted'>Exploration evidence is used as vocabulary evidence first. These terms are not jobs and do not mutate search profiles.</p>"
        f"<div class='risk-list'>{''.join(rows)}</div>"
        "</section>"
    )


def render_false_negative_risk_section(
    false_negative_risks: list[WorkspaceFalseNegativeRisk] | None,
) -> str:
    risks = false_negative_risks or []
    actionable_risks = [risk for risk in risks if risk.risk_level in {"critical", "high", "medium"}]
    if not actionable_risks:
        return ""

    rows: list[str] = []
    for risk in actionable_risks[:5]:
        terms = ", ".join(risk.suggested_search_terms[:3]) if risk.suggested_search_terms else "-"
        rows.append(
            "<article class='risk-row'>"
            "<div>"
            f"<span class='risk-badge {h(risk_badge_class(risk.risk_level))}'>{h(risk.risk_level.upper())}</span>"
            f"<strong>{h(risk.company_name)}</strong>"
            f"<p class='muted'>{h(risk.reason)}</p>"
            "</div>"
            "<div class='risk-row-facts'>"
            f"<span>{h(risk.sighting_count)} sightings</span>"
            f"<span>{h(risk.recent_sighting_count)} recent</span>"
            f"<span>last: {h(humanize_timestamp(risk.last_observed_at))}</span>"
            f"<span>terms: {h(terms)}</span>"
            "</div>"
            "</article>"
        )

    highest = actionable_risks[0].risk_level.upper()
    return (
        "<section class='risk-section compact-risk panel'>"
        "<div class='section-heading'>"
        "<div><span class='eyebrow'>Search Intelligence</span>"
        "<h3>False Negative Risk</h3></div>"
        f"<span class='status-pill warn'>{h(len(actionable_risks))} open · highest {h(highest)}</span>"
        "</div>"
        "<p class='muted'>Market evidence contradicts unresolved or blocked employer-origin decisions. Use this as the short worklist; candidate details stay below.</p>"
        f"<div class='risk-list'>{''.join(rows)}</div>"
        "</section>"
    )


def render_reassessment_queue_section(
    reassessment_items: list[WorkspaceReassessmentItem] | None,
) -> str:
    items = reassessment_items or []
    open_items = [item for item in items if item.status == "open"]
    if not open_items:
        return ""

    rows: list[str] = []
    for item in open_items[:8]:
        terms = ", ".join(item.suggested_search_terms[:4]) if item.suggested_search_terms else "-"
        rows.append(
            "<article class='reassessment-row'>"
            "<div>"
            f"<strong>{h(item.company_name)}</strong>"
            f"<p class='muted'>{h(item.trigger_reason)}</p>"
            "</div>"
            "<div class='risk-row-facts'>"
            f"<span>risk: {h(item.risk_level.upper())}</span>"
            f"<span>priority: {h(item.priority)}</span>"
            f"<span>terms: {h(terms)}</span>"
            f"<span>updated: {h(humanize_timestamp(item.updated_at))}</span>"
            "</div>"
            "</article>"
        )

    return (
        "<section class='risk-section compact-risk panel'>"
        "<div class='section-heading'>"
        "<div><span class='eyebrow'>Search Intelligence</span>"
        "<h3>Reassessment Queue</h3></div>"
        f"<span class='status-pill warn'>{h(len(open_items))} open</span>"
        "</div>"
        "<p class='muted'>False-negative findings that need source/profile reassessment before more connector expansion.</p>"
        f"<div class='risk-list'>{''.join(rows)}</div>"
        "</section>"
    )


def render_search_intelligence_learning_section(
    confidence_items: list[WorkspaceSearchTermConfidence] | None,
) -> str:
    items = confidence_items or []
    if not items:
        return ""

    rows: list[str] = []
    for item in items[:8]:
        source_family = item.source_family_candidate or "all sources"
        rows.append(
            "<article class='reassessment-row'>"
            "<div>"
            f"<strong>{h(item.suggested_term)}</strong>"
            f"<p class='muted'>source family: {h(source_family)}</p>"
            "</div>"
            "<div class='risk-row-facts'>"
            f"<span>confidence: {h(item.confidence_score)}%</span>"
            f"<span>level: {h(item.confidence_level.title())}</span>"
            f"<span>sample: {h(item.sample_size)}</span>"
            f"<span>success: {h(item.success_count)}</span>"
            f"<span>failed/noisy: {h(item.failure_count + item.noise_count)}</span>"
            "</div>"
            "</article>"
        )

    return (
        "<section class='risk-section compact-risk panel'>"
        "<div class='section-heading'>"
        "<div><span class='eyebrow'>Search Intelligence</span>"
        "<h3>Learning Loop</h3></div>"
        f"<span class='status-pill warn'>{h(len(items))} learned term(s)</span>"
        "</div>"
        "<p class='muted'>Validated suggestions turn into source-specific confidence. This is review state only; active search profiles are not changed automatically.</p>"
        f"<div class='risk-list'>{''.join(rows)}</div>"
        "</section>"
    )


def render_search_strategy_recommendation_section(
    recommendations: list[WorkspaceSearchStrategyRecommendation] | None,
) -> str:
    items = recommendations or []
    open_items = [item for item in items if item.recommendation_status in {"pending_review", "auto_eligible"}]
    if not open_items:
        return ""

    rows: list[str] = []
    for item in open_items[:8]:
        fn_risk = item.false_negative_risk_level.upper() if item.false_negative_risk_level else "-"
        rows.append(
            "<article class='reassessment-row'>"
            "<div>"
            f"<strong>{h(item.company_key)} · {h(item.suggested_term)}</strong>"
            f"<p class='muted'>{h(item.reason)}</p>"
            "</div>"
            "<div class='risk-row-facts'>"
            f"<span>{h(humanize_identifier(item.recommendation_type))}</span>"
            f"<span>status: {h(humanize_state(item.recommendation_status))}</span>"
            f"<span>guardrail: {h(humanize_identifier(item.guardrail_decision))}</span>"
            f"<span>confidence: {h(item.confidence_score)}%</span>"
            f"<span>sample: {h(item.sample_size)}</span>"
            f"<span>false-negative: {h(fn_risk)}</span>"
            "</div>"
            "</article>"
        )

    auto_count = sum(1 for item in open_items if item.recommendation_status == "auto_eligible")
    return (
        "<section class='risk-section compact-risk panel'>"
        "<div class='section-heading'>"
        "<div><span class='eyebrow'>Search Intelligence</span>"
        "<h3>Strategy Recommendations</h3></div>"
        f"<span class='status-pill warn'>{h(len(open_items))} open · {h(auto_count)} auto-eligible</span>"
        "</div>"
        "<p class='muted'>Guardrailed recommendations turn validated learning into controlled search-strategy adaptation. They do not mutate search profiles yet.</p>"
        f"<div class='risk-list'>{''.join(rows)}</div>"
        "</section>"
    )


def render_trial_terms_section(
    trial_terms: list[WorkspaceTrialTerm] | None,
) -> str:
    items = trial_terms or []
    active_items = [item for item in items if item.trial_status == "active"]
    if not active_items:
        return ""

    rows: list[str] = []
    for item in active_items[:8]:
        source_family = item.source_family_candidate or item.company_key
        rows.append(
            "<article class='reassessment-row'>"
            "<div>"
            f"<strong>{h(item.company_key)} · {h(item.suggested_term)}</strong>"
            f"<p class='muted'>bounded trial for source family: {h(source_family)}</p>"
            "</div>"
            "<div class='risk-row-facts'>"
            f"<span>status: {h(humanize_state(item.trial_status))}</span>"
            f"<span>guardrail: {h(humanize_identifier(item.guardrail_decision))}</span>"
            f"<span>max volume: {h(item.max_result_volume)}</span>"
            f"<span>max noise: {h(item.max_noise_rate)}</span>"
            f"<span>expires: {h(humanize_timestamp(item.trial_expires_at))}</span>"
            "</div>"
            "</article>"
        )

    return (
        "<section class='risk-section compact-risk panel'>"
        "<div class='section-heading'>"
        "<div><span class='eyebrow'>Search Intelligence</span>"
        "<h3>Controlled Trials</h3></div>"
        f"<span class='status-pill warn'>{h(len(active_items))} active</span>"
        "</div>"
        "<p class='muted'>Approved strategy recommendations become bounded trial terms here. They are scoped, expiring and not permanent search-profile mutations.</p>"
        f"<div class='risk-list'>{''.join(rows)}</div>"
        "</section>"
    )


def render_workspace_html(
    queue_items: list[Any],
    gates_by_candidate_id: Mapping[int, Mapping[str, object]],
    *,
    target_location: str,
    reviewed_by: str,
    write_actions_enabled: bool,
    flash_message: str | None = None,
    selected_view: str = "all",
    search_query: str = "",
    false_negative_risks: list[WorkspaceFalseNegativeRisk] | None = None,
    reassessment_items: list[WorkspaceReassessmentItem] | None = None,
    confidence_items: list[WorkspaceSearchTermConfidence] | None = None,
    strategy_recommendations: list[WorkspaceSearchStrategyRecommendation] | None = None,
    trial_terms: list[WorkspaceTrialTerm] | None = None,
    vocabulary_items: list[WorkspaceCompanyVocabulary] | None = None,
) -> str:
    selected = normalize_view(selected_view)
    filtered_items = filter_workspace_items(
        queue_items,
        selected_view=selected,
        search_query=search_query,
    )
    view_counts = workspace_view_counts(queue_items)
    view_counts["false_negative"] = len([risk for risk in (false_negative_risks or []) if risk.risk_level in {"critical", "high", "medium"}])
    view_counts["reassessment"] = len([item for item in (reassessment_items or []) if item.status == "open"])
    view_counts["learning"] = len(confidence_items or [])
    view_counts["vocabulary"] = len({item.company_key for item in (vocabulary_items or [])})
    view_counts["strategy"] = len([item for item in (strategy_recommendations or []) if item.recommendation_status in {"pending_review", "auto_eligible"}])
    view_counts["trials"] = len([item for item in (trial_terms or []) if item.trial_status == "active"])

    needs_approval = sum(1 for item in queue_items if workspace_action_for_item(item, target_location=target_location, reviewed_by=reviewed_by))
    actionable = sum(1 for item in queue_items if item.command)
    blocked = view_counts.get("review_required", 0)
    monitored = view_counts.get("active", 0)

    if selected == "false_negative":
        candidate_cards = (
            "<div class='empty-state'>"
            "<strong>False-negative worklist mode.</strong>"
            "<p>The risk worklist above is the primary view here. Switch to Review required for full candidate gate details.</p>"
            "</div>"
        )
    elif selected == "reassessment":
        candidate_cards = (
            "<div class='empty-state'>"
            "<strong>Reassessment worklist mode.</strong>"
            "<p>The reassessment queue above is the primary view here. Use the suggested terms to guide bounded source/profile review.</p>"
            "</div>"
        )
    elif selected == "learning":
        candidate_cards = (
            "<div class='empty-state'>"
            "<strong>Learning loop mode.</strong>"
            "<p>The learning summary above is the primary view here. Suggestions remain review artifacts until explicitly validated and accepted.</p>"
            "</div>"
        )
    elif selected == "strategy":
        candidate_cards = (
            "<div class='empty-state'>"
            "<strong>Strategy recommendation mode.</strong>"
            "<p>The strategy recommendation worklist above is the primary view here. Search profiles are not changed automatically in this mode.</p>"
            "</div>"
        )
    elif selected == "trials":
        candidate_cards = (
            "<div class='empty-state'>"
            "<strong>Controlled trial mode.</strong>"
            "<p>The active trial list above is the primary view here. Trials expire and remain separate from permanent search profiles.</p>"
            "</div>"
        )
    elif selected == "trials":
        candidate_cards = (
            "<div class='empty-state'>"
            "<strong>Controlled trial mode.</strong>"
            "<p>The active trial list above is the primary view here. Trials expire and remain separate from permanent search profiles.</p>"
            "</div>"
        )
    else:
        cards = [
            render_candidate_card(
                item,
                gates_by_candidate_id.get(item.candidate.candidate_id, {}),
                target_location=target_location,
                reviewed_by=reviewed_by,
                write_actions_enabled=write_actions_enabled,
            )
            for item in filtered_items
        ]
        candidate_cards = "".join(cards) if cards else render_empty_state(selected_view=selected, search_query=search_query)

    flash = f"<div class='flash'>{h(flash_message)}</div>" if flash_message else ""
    mode = "write-enabled" if write_actions_enabled else "read-only"
    mode_badge_class = "write" if write_actions_enabled else "read"
    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Employer-Origin Approval Workspace</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #06111f;
  --bg-2: #081827;
  --panel: rgba(8, 24, 39, .94);
  --panel-2: rgba(9, 30, 48, .78);
  --line: rgba(99, 159, 199, .28);
  --line-strong: rgba(56, 189, 248, .50);
  --text: #ecf7ff;
  --muted: #9db8cc;
  --cyan: #22d3ee;
  --cyan-soft: rgba(34, 211, 238, .12);
  --blue: #38bdf8;
  --green: #70e36b;
  --amber: #f5b642;
  --red: #ff5d5d;
  --shadow: 0 16px 48px rgba(0, 0, 0, .32);
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; background: radial-gradient(circle at 18% 0%, rgba(34, 211, 238, .12), transparent 28%), linear-gradient(135deg, var(--bg), #030914 72%); color: var(--text); }}
body::before {{ content: ''; position: fixed; inset: 0; pointer-events: none; background-image: linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px); background-size: 34px 34px; mask-image: linear-gradient(to bottom, rgba(0,0,0,.9), transparent 82%); }}
main {{ max-width: 1280px; margin: 0 auto; padding: 1.25rem 1.5rem 2rem; position: relative; }}
.brandbar {{ display: flex; justify-content: space-between; gap: 1rem; align-items: center; padding: .6rem 0 1rem; border-bottom: 1px solid var(--line); }}
.brand-left {{ display: flex; gap: .9rem; align-items: center; }}
.logo {{ width: 42px; height: 42px; display: grid; place-items: center; border: 2px solid var(--cyan); color: var(--cyan); clip-path: polygon(25% 5%, 75% 5%, 100% 50%, 75% 95%, 25% 95%, 0 50%); box-shadow: 0 0 24px rgba(34, 211, 238, .22); font-weight: 800; }}
h1 {{ margin: 0; font-size: clamp(1.25rem, 2.4vw, 1.9rem); letter-spacing: .02em; }}
.subtitle {{ margin: .2rem 0 0; color: var(--muted); font-size: .92rem; }}
.mode-panel {{ display: flex; gap: .7rem; align-items: center; flex-wrap: wrap; justify-content: flex-end; }}
.mode-pill, .status-pill, .chip {{ border: 1px solid var(--line); border-radius: 999px; padding: .35rem .65rem; font-size: .82rem; white-space: nowrap; }}
.mode-pill.read {{ color: var(--cyan); border-color: var(--line-strong); background: var(--cyan-soft); }}
.mode-pill.write {{ color: var(--amber); border-color: rgba(245, 182, 66, .62); background: rgba(245, 182, 66, .10); }}
.hero {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 1rem; align-items: end; padding: 1.3rem 0 1rem; }}
.hero h2 {{ margin: 0; font-size: 1.05rem; letter-spacing: .08em; text-transform: uppercase; color: #c9efff; }}
.hero p {{ margin: .35rem 0 0; color: var(--muted); max-width: 74ch; }}
.summary {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .85rem; margin: .75rem 0 1rem; }}
.metric, .candidate-card {{ background: linear-gradient(180deg, var(--panel), rgba(5, 16, 29, .96)); border: 1px solid var(--line); border-radius: 14px; box-shadow: var(--shadow); }}
.metric {{ padding: .85rem .95rem; position: relative; overflow: hidden; }}
.metric::after {{ content: ''; position: absolute; inset: auto .8rem 0 .8rem; height: 2px; background: linear-gradient(90deg, transparent, var(--cyan), transparent); opacity: .42; }}
.metric strong {{ display: block; font-size: 1.35rem; line-height: 1; }}
.metric span {{ display: block; margin-top: .3rem; color: var(--muted); font-size: .82rem; }}
.section-title {{ display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; margin: 1rem 0 .65rem; }}
.section-title h3 {{ margin: 0; text-transform: uppercase; letter-spacing: .08em; color: #bfeaff; font-size: .9rem; }}
.section-title p {{ margin: 0; color: var(--muted); font-size: .86rem; }}
.workspace-controls {{ display: grid; gap: .75rem; margin: .75rem 0 1rem; }}
.view-tabs {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .55rem; }}
.view-tab {{ display: flex; justify-content: space-between; align-items: center; gap: .5rem; color: var(--muted); text-decoration: none; border: 1px solid var(--line); background: rgba(4, 14, 25, .44); border-radius: 12px; padding: .55rem .65rem; }}
.view-tab strong {{ color: var(--text); }}
.view-tab.active {{ color: var(--cyan); border-color: var(--line-strong); background: var(--cyan-soft); }}
.search-form {{ display: flex; flex-wrap: wrap; align-items: end; gap: .65rem; }}
.clear-filter {{ color: var(--cyan); text-decoration: none; padding: .55rem .2rem; }}
.result-count {{ margin: 0; color: var(--muted); font-size: .84rem; }}
.empty-state {{ border: 1px dashed var(--line); border-radius: 14px; padding: 1rem; color: var(--muted); background: rgba(4, 14, 25, .36); }}
.empty-state strong {{ color: var(--text); }}
.candidate-list {{ display: grid; gap: .75rem; }}
.candidate-card {{ padding: .85rem .95rem; }}
.candidate-header {{ display: flex; justify-content: space-between; gap: .8rem; align-items: flex-start; }}
.candidate-header h2 {{ margin: 0; font-size: 1.1rem; }}
.muted {{ color: var(--muted); }}
.candidate-header .muted {{ margin: .18rem 0 0; font-size: .85rem; }}
.status-pill {{ color: var(--muted); }}
.needs-approval .status-pill {{ border-color: rgba(245, 182, 66, .75); color: var(--amber); background: rgba(245, 182, 66, .08); }}
.blocked .status-pill {{ border-color: rgba(255, 93, 93, .72); color: #ff8e8e; background: rgba(255, 93, 93, .07); }}
.actionable .status-pill {{ border-color: rgba(34, 211, 238, .72); color: var(--cyan); background: var(--cyan-soft); }}
.monitor .status-pill {{ border-color: rgba(112, 227, 107, .72); color: var(--green); background: rgba(112, 227, 107, .08); }}
.candidate-grid {{ display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)); gap: .75rem; margin: .75rem 0; }}
.candidate-grid p {{ margin: 0; padding: .55rem .65rem; border: 1px solid rgba(99, 159, 199, .20); border-radius: 10px; background: rgba(4, 14, 25, .42); }}
.label {{ display: block; color: var(--muted); font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; margin-bottom: .22rem; }}
.progress-block {{ margin-top: .45rem; }}
.progress-row {{ display: flex; justify-content: space-between; gap: .75rem; margin-bottom: .35rem; color: #dff7ff; font-size: .88rem; }}
.progress {{ height: .48rem; background: rgba(2, 8, 17, .95); border: 1px solid rgba(99, 159, 199, .24); border-radius: 999px; overflow: hidden; }}
.progress span {{ display: block; height: 100%; background: linear-gradient(90deg, var(--cyan), var(--green)); box-shadow: 0 0 16px rgba(34, 211, 238, .35); }}
.gate-chips {{ display: flex; flex-wrap: wrap; gap: .35rem; margin-top: .45rem; }}
.chip {{ padding: .18rem .48rem; font-size: .74rem; background: rgba(5, 16, 29, .58); }}
.chip.ok {{ border-color: rgba(112, 227, 107, .62); color: var(--green); }}
.chip.warn {{ border-color: rgba(245, 182, 66, .62); color: var(--amber); }}
.chip.bad {{ border-color: rgba(255, 93, 93, .62); color: #ff8e8e; }}
.phase-tracker {{ display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); list-style: none; margin: .85rem 0 .4rem; padding: 0; gap: .35rem; }}
.phase-tracker li {{ display: flex; flex-direction: column; gap: .25rem; color: var(--muted); font-size: .72rem; min-width: 0; }}
.phase-tracker span {{ display: block; height: .25rem; border-radius: 999px; background: rgba(99, 159, 199, .22); }}
.phase-tracker li.done span {{ background: rgba(112, 227, 107, .72); }}
.phase-tracker li.current {{ color: #e8faff; }}
.phase-tracker li.current span {{ background: var(--cyan); box-shadow: 0 0 16px rgba(34, 211, 238, .50); }}
.reason {{ margin: .65rem 0 .35rem; color: #dceffd; }}
.review-panel, .approval-panel, .command-panel, .flash {{ border: 1px solid var(--line); border-radius: 12px; padding: .8rem; margin: .65rem 0; background: var(--panel-2); }}
.review-panel {{ border-color: rgba(245, 182, 66, .56); background: rgba(245, 182, 66, .07); }}
.approval-panel {{ border-color: rgba(34, 211, 238, .46); background: rgba(34, 211, 238, .07); }}
.flash {{ border-color: var(--line-strong); white-space: pre-wrap; }}
.warning {{ color: var(--amber); }}
pre {{ overflow: auto; background: rgba(2, 8, 17, .96); padding: .7rem; border-radius: 10px; border: 1px solid rgba(99, 159, 199, .24); color: #bfeaff; }}
.approval-form {{ display: flex; flex-wrap: wrap; gap: .65rem; align-items: end; }}
input {{ padding: .55rem .6rem; border-radius: 9px; border: 1px solid var(--line); min-width: 220px; background: #07111f; color: var(--text); }}
button {{ padding: .62rem .85rem; border-radius: 10px; border: 1px solid var(--line-strong); font-weight: 750; cursor: pointer; background: rgba(34, 211, 238, .12); color: var(--text); }}
button:hover {{ border-color: var(--cyan); }}
button:disabled {{ opacity: .45; cursor: not-allowed; }}
.stop-button {{ background: transparent; border-color: rgba(99, 159, 199, .35); color: var(--muted); }}
details.gate-details {{ margin-top: .55rem; }}
summary {{ cursor: pointer; color: #bfeaff; }}
table {{ width: 100%; border-collapse: collapse; margin-top: .65rem; }}
th, td {{ text-align: left; border-bottom: 1px solid rgba(99, 159, 199, .20); padding: .42rem; vertical-align: top; }}
th {{ color: #bfeaff; font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; }}
code {{ color: #d7f4ff; }}
.footer-note {{ display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap; margin-top: 1.2rem; padding-top: .8rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .82rem; }}
@media (max-width: 1000px) {{ .view-tabs {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .risk-row {{ grid-template-columns: 1fr; }} .risk-row-facts {{ justify-content: flex-start; }} }}
@media (max-width: 900px) {{ .summary {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .hero, .brandbar {{ grid-template-columns: 1fr; display: block; }} .mode-panel {{ justify-content: flex-start; margin-top: .8rem; }} }}
@media (max-width: 680px) {{ main {{ padding: .9rem; }} .summary, .candidate-grid, .view-tabs {{ grid-template-columns: 1fr; }} .candidate-header {{ flex-direction: column; }} .phase-tracker {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} input {{ min-width: 100%; }} }}
.risk-section {{ margin: 1rem 0; }}
.section-heading {{ display: flex; justify-content: space-between; gap: 1rem; align-items: center; margin-bottom: .75rem; }}
.section-heading h3 {{ margin: .15rem 0 0; }}
.risk-list {{ display: grid; gap: .45rem; }}
.risk-row, .reassessment-row {{ display: grid; grid-template-columns: minmax(220px, 1.1fr) minmax(280px, 1.4fr); gap: .75rem; align-items: center; border: 1px solid rgba(99, 159, 199, .24); border-radius: 14px; padding: .65rem .75rem; background: rgba(245, 182, 66, .045); }}
.risk-row strong {{ display: inline-block; margin-left: .45rem; }}
.reassessment-row strong {{ display: inline-block; }}
.risk-row p, .reassessment-row p {{ margin: .28rem 0 0; }}
.risk-row-facts {{ display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .35rem; }}
.risk-badge {{ display: inline-flex; border: 1px solid var(--line); border-radius: 999px; padding: .28rem .58rem; font-size: .78rem; font-weight: 800; }}
.risk-badge.bad {{ color: var(--red); border-color: rgba(255, 93, 93, .58); }}
.risk-badge.warn {{ color: var(--amber); border-color: rgba(245, 182, 66, .62); }}
.risk-badge.ok {{ color: var(--green); border-color: rgba(112, 227, 107, .55); }}
.risk-facts {{ display: flex; flex-wrap: wrap; gap: .4rem; margin: .65rem 0; }}
.risk-facts span {{ border: 1px solid var(--line); border-radius: 999px; padding: .2rem .5rem; color: var(--muted); font-size: .78rem; }}
</style>
</head>
<body>
<main>
  <header class='brandbar'>
    <div class='brand-left'>
      <div class='logo'>JP</div>
      <div>
        <h1>Job-Pipeline Approval Workspace</h1>
        <p class='subtitle'>Employer-Origin Agents · Sweet Spot — Balanced Intelligence</p>
      </div>
    </div>
    <div class='mode-panel'>
      <span class='mode-pill {mode_badge_class}'>Mode: {h(mode)}</span>
      <form method='post' action='/actions/shutdown'><button class='stop-button' type='submit'>Stop workspace</button></form>
    </div>
  </header>

  <section class='hero'>
    <div>
      <h2>Approval Control Surface</h2>
      <p>This local workspace shows what is new, what is blocked, and where your explicit approval is required. It never activates sources, writes Bronze rows, registers schedulers or uses CSV/export files as inputs.</p>
    </div>
  </section>

  {flash}

  <section class='summary' aria-label='Workspace summary'>
    <div class='metric'><strong>{len(queue_items)}</strong><span>Candidates</span></div>
    <div class='metric'><strong>{needs_approval}</strong><span>Approval actions</span></div>
    <div class='metric'><strong>{blocked}</strong><span>Need review</span></div>
    <div class='metric'><strong>{monitored}</strong><span>Monitoring</span></div>
  </section>

  <section class='section-title'>
    <h3>Candidate Landscape</h3>
    <p>{actionable} actionable console command(s) available through the existing agent chain</p>
  </section>

  {render_false_negative_risk_section(false_negative_risks)}

  {render_reassessment_queue_section(reassessment_items)}
  {render_search_intelligence_learning_section(confidence_items)}
  {render_company_vocabulary_section(vocabulary_items)}
  {render_search_strategy_recommendation_section(strategy_recommendations)}
  {render_trial_terms_section(trial_terms)}

  {render_view_controls(selected_view=selected, search_query=search_query, counts=view_counts, visible_count=len(filtered_items), total_count=len(queue_items))}

  <section class='candidate-list'>
    {candidate_cards}
  </section>

  <footer class='footer-note'>
    <span>Intelligence by design: better decisions from bounded, reviewable gates.</span>
    <span>StepStone remains a bounded discovery signal with feed-forward candidate suppression.</span>
  </footer>
</main>
</body>
</html>"""
