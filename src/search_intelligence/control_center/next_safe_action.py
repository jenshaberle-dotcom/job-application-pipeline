from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

from src.search_intelligence.employer_origin_gate_registry import OFFICIAL_EMPLOYER_ORIGIN_GATES
from src.search_intelligence.origin_url_policy import has_disallowed_source_url_shape

BUILD_APPROVAL_TOKEN = "approve_connector_build"
REGISTRATION_APPROVAL_TOKEN = "approve_connector_registration"
EVIDENCE_REPAIR_TOKEN = "run_evidence_repair"
CONTINUE_CANDIDATE_REVIEW_TOKEN = "continue_candidate_review"
CONNECTOR_VALIDATION_TOKEN = "run_connector_validation"
NEXT_SAFE_ACTION_TOKEN = "run_next_safe_action"
EARLY_GATE_NAMES = {gate.gate_name for gate in OFFICIAL_EMPLOYER_ORIGIN_GATES if gate.gate_order <= 7}
TERMINAL_GATE_DECISIONS = {"abort_documented", "manual_review_required"}
TERMINAL_GATE_STATUSES = {"failed", "manual_review_required", "deferred"}
TERMINAL_CANDIDATE_STATUSES = {"abort_documented", "disabled", "deprecated"}


@dataclass(frozen=True)
class NextSafeAction:
    action_id: str
    label: str
    button_label: str
    summary: str
    may: str
    will_not: str
    tone: str = "neutral"
    action_path: str | None = None
    approval_token: str | None = None
    show_action: bool = False

    def to_display_dict(self) -> dict[str, object]:
        return asdict(self)


def _value(item: object, name: str, default: object = None) -> object:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _normalized(item: object, *names: str) -> str:
    for name in names:
        value = str(_value(item, name, "") or "").strip().lower().replace(" ", "_")
        if value:
            return value
    return ""


def _passed_count(candidate: object) -> int:
    return int(_value(candidate, "gate_passed_count", 0) or _value(candidate, "passed_gate_count", 0) or 0)


def _is_active(candidate: object) -> bool:
    return _normalized(candidate, "status", "candidate_status") == "active_controlled"


def _needs_build_approval(candidate: object) -> bool:
    return (
        _normalized(candidate, "build_status") == "build_approval_required"
        and _normalized(candidate, "build_recommendation") == "request_explicit_build_approval"
    )


def _needs_registration_approval(candidate: object) -> bool:
    return (
        _normalized(candidate, "connector_validation_status") == "passed"
        and _normalized(candidate, "connector_validation_decision") == "ready_for_final_approval"
        and _normalized(candidate, "final_approval_decision") != "approve_connector_registration"
        and not _is_active(candidate)
    )


def _can_run_connector_validation(candidate: object) -> bool:
    if _is_active(candidate):
        return False

    status = _normalized(candidate, "status", "candidate_status")
    stage = _normalized(candidate, "current_stage", "stage")
    display_stage = _normalized(candidate, "display_stage")
    passed = _passed_count(candidate)

    return (
        status == "connector_candidate"
        or stage == "connector_candidate"
        or display_stage == "connector_candidate"
        or passed >= 10
    )



def _blocking_gate(candidate: object) -> str:
    return _normalized(candidate, "latest_blocking_gate", "blocking_gate")


def _blocking_decision(candidate: object) -> str:
    return _normalized(candidate, "latest_blocking_decision", "blocking_decision")


def _blocking_status(candidate: object) -> str:
    return _normalized(candidate, "latest_blocking_status", "blocking_gate_status")


def _blocking_reason(candidate: object) -> str:
    return str(_value(candidate, "latest_blocking_reason", "") or _value(candidate, "blocker_reason", "") or "").strip()


def _candidate_status(candidate: object) -> str:
    return _normalized(candidate, "status", "candidate_status")


def _candidate_url(candidate: object) -> str:
    return str(_value(candidate, "candidate_url", "") or "").strip()


def _source_discovery_stop_is_recoverable(candidate: object) -> bool:
    if _blocking_gate(candidate) != "source_discovery":
        return False
    if _blocking_decision(candidate) != "abort_documented":
        return False
    url = _candidate_url(candidate)
    return bool(url) and has_disallowed_source_url_shape(url) is None


def _source_url_recovery_action(candidate: object) -> NextSafeAction:
    return NextSafeAction(
        action_id="run_initial_gate_review",
        label="Re-run source URL gate",
        button_label="Run source URL recovery",
        summary=(
            "The previous source-discovery stop is recoverable: the persisted URL is now accepted by "
            "the shared URL policy. Re-run the bounded gate review instead of leaving the candidate parked."
        ),
        may="Re-run the bounded company/source/gate review for the persisted candidate URL and update existing gate reviews.",
        will_not="Build connector artifacts, register connectors, activate sources, write Bronze records or change scheduler configuration.",
        tone="warn",
        action_path="/actions/run-next-safe-action",
        approval_token=NEXT_SAFE_ACTION_TOKEN,
        show_action=True,
    )




def _technical_reachability_stop_is_recoverable(candidate: object) -> bool:
    if _blocking_gate(candidate) != "technical_reachability_gate":
        return False
    if _blocking_decision(candidate) != "abort_documented":
        return False
    reason = _blocking_reason(candidate).lower()
    return "http 404" in reason or "not found" in reason or "request failed" in reason


def _technical_reachability_recovery_action(candidate: object) -> NextSafeAction:
    return NextSafeAction(
        action_id="run_source_url_recovery",
        label="Run source URL recovery",
        button_label="Run source URL recovery",
        summary=(
            "Technical reachability stopped on the persisted candidate URL. The next safe product step is "
            "bounded source URL recovery: probe a small set of company-related public career/job URLs, "
            "update the candidate URL if one is reachable, then rerun the early gate review."
        ),
        may="Probe bounded company-related career/job URL candidates and update this candidate's URL before rerunning early gates.",
        will_not="Build connector artifacts, register connectors, activate sources, write Bronze records, use exports as inputs or change scheduler configuration.",
        tone="warn",
        action_path="/actions/run-next-safe-action",
        approval_token=NEXT_SAFE_ACTION_TOKEN,
        show_action=True,
    )


def _relevance_stop_is_recoverable(candidate: object) -> bool:
    if _blocking_gate(candidate) != "relevance_gate":
        return False
    if _blocking_decision(candidate) != "manual_review_required":
        return False
    reason = _blocking_reason(candidate).lower()
    return (
        "bounded preview" in reason
        or "profile-term evidence" in reason
        or "target-location or remote" in reason
    )


def _relevance_evidence_probe_action(candidate: object) -> NextSafeAction:
    return NextSafeAction(
        action_id="run_autonomous_relevance_discovery",
        label="Run autonomous relevance discovery",
        button_label="Run autonomous relevance discovery",
        summary=(
            "The listing/source preview did not expose enough relevance evidence. The next safe step is "
            "autonomous bounded job-detail discovery and signal learning over same-/related-host job or search pages."
        ),
        may="Probe bounded job/search pages, persist autonomous job-detail evidence, learn profile/location/remote signals from accepted evidence, and update only the relevance gate.",
        will_not="Build connector artifacts, register connectors, activate sources, write Bronze records, use exports as inputs or change scheduler configuration.",
        tone="warn",
        action_path="/actions/run-next-safe-action",
        approval_token=NEXT_SAFE_ACTION_TOKEN,
        show_action=True,
    )


def _has_terminal_blocker(candidate: object) -> bool:
    decision = _blocking_decision(candidate)
    status = _blocking_status(candidate)
    candidate_status = _candidate_status(candidate)
    return (
        decision in TERMINAL_GATE_DECISIONS
        or status in TERMINAL_GATE_STATUSES
        or candidate_status in TERMINAL_CANDIDATE_STATUSES
    )


def _terminal_blocker_action(candidate: object) -> NextSafeAction:
    blocker = _blocking_gate(candidate) or "current_gate"
    decision = _blocking_decision(candidate) or _blocking_status(candidate) or _candidate_status(candidate) or "blocked"
    reason = _blocking_reason(candidate)
    reason_text = f" Reason: {reason}" if reason else ""
    label = "No safe automated action"
    if decision == "manual_review_required":
        label = "Human review required"
    return NextSafeAction(
        action_id="no_safe_automated_action",
        label=label,
        button_label="No automatic action",
        summary=(
            f"{blocker.replace('_', ' ').capitalize()} stopped with {decision}."
            f"{reason_text} The orchestrator will not rerun the same automated step."
        ),
        may="Guide a human review, parking decision or corrected public source-URL selection.",
        will_not="Rerun the same gate agent, perform detail repair, register connectors, activate sources, write Bronze records or change scheduler configuration.",
        tone="bad" if decision == "abort_documented" else "warn",
        show_action=False,
    )


def determine_next_safe_action(candidate: object) -> NextSafeAction:
    """Return the one primary safe action the Control Center should show.

    This function is deliberately display-/workflow-oriented. It prevents the
    GUI from treating every blocking gate as an evidence-repair problem. A
    candidate with no early gates passed should run the initial bounded gate
    review before any detail-evidence repair is attempted.
    """

    if _is_active(candidate):
        return NextSafeAction(
            action_id="monitor_existing_controlled_source",
            label="Monitor existing controlled source",
            button_label="Monitor only",
            summary="Controlled source is active. Keep it visible for health, freshness and source-value monitoring.",
            may="Read source health, lifecycle and source-value signals.",
            will_not="Run agents, activate sources, write Bronze records or change scheduler configuration.",
            tone="ok",
        )

    if _needs_registration_approval(candidate):
        return NextSafeAction(
            action_id="approve_connector_registration",
            label="Approve registration gate",
            button_label="Review approval action",
            summary="Connector validation is passed; the next safe step is explicit registration approval.",
            may="Persist the final registration approval gate after explicit human confirmation.",
            will_not="Activate sources, write Bronze records, change scheduler configuration or bypass controlled activation.",
            tone="warn",
            action_path="/actions/approve-registration",
            approval_token=REGISTRATION_APPROVAL_TOKEN,
            show_action=True,
        )

    if _can_run_connector_validation(candidate):
        return NextSafeAction(
            action_id="run_connector_validation",
            label="Validate connector",
            button_label="Run connector validation",
            summary="Evidence and connector-candidate gates are passed. The next safe step is connector validation, not another generic review rerun.",
            may="Run connector validation, refresh validation-gate evidence and persist an action-run audit entry.",
            will_not="Activate sources, write Bronze records, change scheduler configuration, merge PRs or bypass explicit approval gates.",
            tone="ok",
            action_path="/actions/run-connector-validation",
            approval_token=CONNECTOR_VALIDATION_TOKEN,
            show_action=True,
        )

    passed = _passed_count(candidate)
    blocker = _blocking_gate(candidate)

    if blocker in EARLY_GATE_NAMES and _has_terminal_blocker(candidate):
        if _source_discovery_stop_is_recoverable(candidate):
            return _source_url_recovery_action(candidate)
        if _technical_reachability_stop_is_recoverable(candidate):
            return _technical_reachability_recovery_action(candidate)
        if _relevance_stop_is_recoverable(candidate):
            return _relevance_evidence_probe_action(candidate)
        return _terminal_blocker_action(candidate)

    if passed < 7:
        return NextSafeAction(
            action_id="run_initial_gate_review",
            label="Run initial gate review",
            button_label="Run next safe action",
            summary="Early gates are not complete yet. The safe next step is bounded company/source/gate review, not detail-evidence repair.",
            may="Run the initial employer-origin gate agent for the persisted candidate and refresh early gate evidence.",
            will_not="Run connector registration, activate sources, write Bronze records, change scheduler configuration or skip detail evidence gates.",
            tone="warn",
            action_path="/actions/run-next-safe-action",
            approval_token=NEXT_SAFE_ACTION_TOKEN,
            show_action=True,
        )

    if blocker == "detail_evidence_gate":
        if _has_terminal_blocker(candidate):
            return _terminal_blocker_action(candidate)
        return NextSafeAction(
            action_id="run_detail_evidence_repair",
            label="Repair evidence",
            button_label="Review evidence repair action",
            summary="Early gates are already passed; Run bounded evidence repair through the multi-origin detail-evidence path.",
            may="Rerun bounded evidence repair and refresh review/gate evidence.",
            will_not="Register connectors, activate sources, write Bronze records, create scheduler changes or bypass approval gates.",
            tone="warn",
            action_path="/actions/rerun-evidence-repair",
            approval_token=EVIDENCE_REPAIR_TOKEN,
            show_action=True,
        )

    if blocker:
        if _has_terminal_blocker(candidate):
            return _terminal_blocker_action(candidate)
        return NextSafeAction(
            action_id="manual_review_required",
            label="Manual review required",
            button_label="No automatic action",
            summary="A non-detail gate is blocking progress. Inspect the blocker before running another agent.",
            may="Guide manual diagnosis from the persisted blocker reason.",
            will_not="Rerun broad repair logic or advance connector gates blindly.",
            tone="warn",
        )

    if _needs_build_approval(candidate):
        return NextSafeAction(
            action_id="approve_connector_build",
            label="Approve connector build",
            button_label="Review approval action",
            summary="The candidate is waiting for explicit build approval before connector artifacts may be generated.",
            may="Allow bounded connector artifact generation only.",
            will_not="Register connectors, activate sources, write Bronze records, change scheduler configuration or bypass registration approval.",
            tone="warn",
            action_path="/actions/approve-build",
            approval_token=BUILD_APPROVAL_TOKEN,
            show_action=True,
        )

    return NextSafeAction(
        action_id="continue_candidate_review",
        label="Continue candidate review",
        button_label="Run next safe action",
        summary="No explicit blocker is visible; run the next DB-backed bounded candidate-review step.",
        may="Inspect current gate state and run only the next bounded agent step.",
        will_not="Activate sources, write Bronze records, change scheduler configuration, merge PRs or bypass approval gates.",
        tone="neutral",
        action_path="/actions/run-next-safe-action",
        approval_token=NEXT_SAFE_ACTION_TOKEN,
        show_action=True,
    )
