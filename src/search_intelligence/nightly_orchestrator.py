"""Nightly Search Intelligence orchestration planning.

This module is intentionally deterministic and side-effect free. It coordinates
already available Search Intelligence read models into a cycle plan, but it does
not fetch external pages, mutate search profiles, activate sources, register
connectors, write Bronze records or change schedules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class MarketCoverageSummary:
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


@dataclass(frozen=True)
class CandidateLifecycleItem:
    company_key: str
    display_company_name: str
    current_stage: str
    fn_pressure_level: str | None = None
    blocking_gate: str | None = None
    recommended_next_action: str | None = None


@dataclass(frozen=True)
class ApprovalQueueItem:
    approval_type: str
    company_key: str
    display_company_name: str
    current_stage: str
    recommendation: str | None = None


@dataclass(frozen=True)
class OriginDiscoveryItem:
    company_key: str
    company_name: str
    discovery_status: str | None
    decision: str | None
    selected_origin_url: str | None
    blocker_code: str | None = None


@dataclass(frozen=True)
class OrchestratorInput:
    summary: MarketCoverageSummary
    lifecycle_items: tuple[CandidateLifecycleItem, ...]
    approval_items: tuple[ApprovalQueueItem, ...]
    origin_discovery_items: tuple[OriginDiscoveryItem, ...]


@dataclass(frozen=True)
class OrchestratorStep:
    step_order: int
    step_name: str
    step_status: str
    action_mode: str
    recommendation: str
    reason: str
    metrics: dict[str, Any]


@dataclass(frozen=True)
class OrchestratorPlan:
    cycle_name: str
    status: str
    steps: tuple[OrchestratorStep, ...]
    summary: dict[str, Any]
    guardrails: dict[str, bool]


GUARDRAILS: dict[str, bool] = {
    "external_browsing_allowed": False,
    "search_profile_mutation_allowed": False,
    "connector_registration_allowed": False,
    "source_activation_allowed": False,
    "bronze_persistence_allowed": False,
    "scheduler_change_allowed": False,
    "auto_pr_allowed": False,
    "csv_or_export_inputs_used": False,
}


def _as_int(value: Any) -> int:
    if value is None:
        return 0
    return int(value)


def market_coverage_summary_from_row(row: Mapping[str, Any] | None) -> MarketCoverageSummary:
    if not row:
        return MarketCoverageSummary()
    names = MarketCoverageSummary.__dataclass_fields__.keys()
    return MarketCoverageSummary(**{name: _as_int(row.get(name)) for name in names})


def _pressure_attention_count(items: Sequence[CandidateLifecycleItem]) -> int:
    return sum(1 for item in items if item.fn_pressure_level in {"high", "critical"})


def build_orchestrator_plan(inputs: OrchestratorInput) -> OrchestratorPlan:
    """Build the next nightly cycle plan from current Gold-backed state."""

    summary = inputs.summary
    steps: list[OrchestratorStep] = []

    steps.append(
        OrchestratorStep(
            step_order=1,
            step_name="gold_market_coverage_snapshot",
            step_status="ok" if summary.employer_origin_candidate_count else "attention_required",
            action_mode="observe",
            recommendation="Use Gold views as the stable dashboard/control-plane input.",
            reason=(
                "Gold market coverage summary is available."
                if summary.employer_origin_candidate_count
                else "No employer-origin candidates are visible in Gold summary."
            ),
            metrics={
                "employer_origin_candidate_count": summary.employer_origin_candidate_count,
                "active_origin_connector_count": summary.active_origin_connector_count,
                "open_candidate_count": summary.open_candidate_count,
            },
        )
    )

    open_attention = summary.open_candidate_count + summary.gate_reassessment_required_count
    steps.append(
        OrchestratorStep(
            step_order=2,
            step_name="candidate_lifecycle_review",
            step_status="attention_required" if open_attention else "ok",
            action_mode="queue_review" if open_attention else "observe",
            recommendation=(
                "Review open candidates and rerun gate reassessment where learning pressure changed."
                if open_attention
                else "Monitor candidate lifecycle state."
            ),
            reason="Open candidates or gate reassessment pressure are visible in Gold lifecycle state.",
            metrics={
                "open_candidate_count": summary.open_candidate_count,
                "gate_reassessment_required_count": summary.gate_reassessment_required_count,
                "high_or_critical_pressure_items": _pressure_attention_count(inputs.lifecycle_items),
            },
        )
    )

    approvals = len(inputs.approval_items)
    steps.append(
        OrchestratorStep(
            step_order=3,
            step_name="approval_queue_review",
            step_status="attention_required" if approvals else "ok",
            action_mode="manual_approval_required" if approvals else "observe",
            recommendation=(
                "Process approval queue in the Control Center; do not auto-register or auto-activate."
                if approvals
                else "No approval queue action required."
            ),
            reason="Approval-backed connector build requests require explicit human approval.",
            metrics={
                "approval_queue_count": approvals,
                "build_approval_required_count": summary.build_approval_required_count,
                "artifact_generation_allowed_count": summary.connector_artifact_generation_allowed_count,
            },
        )
    )

    missing_origin = [
        item for item in inputs.origin_discovery_items
        if item.discovery_status not in {"selected", "accepted"} or not item.selected_origin_url
    ]
    steps.append(
        OrchestratorStep(
            step_order=4,
            step_name="origin_source_discovery_gate_review",
            step_status="attention_required" if missing_origin else "ok",
            action_mode="queue_review" if missing_origin else "observe",
            recommendation=(
                "Run or review Origin Source Discovery Gate for candidates without a selected origin source."
                if missing_origin
                else "Origin source discovery state is available for reviewed candidates."
            ),
            reason="Connector feasibility should not start from implicit or black-magic origin URLs.",
            metrics={
                "origin_discovery_item_count": len(inputs.origin_discovery_items),
                "origin_discovery_missing_or_unselected_count": len(missing_origin),
            },
        )
    )

    steps.append(
        OrchestratorStep(
            step_order=5,
            step_name="learning_and_novelty_review",
            step_status="attention_required" if summary.actionable_novelty_scope_count else "ok",
            action_mode="recommend" if summary.actionable_novelty_scope_count else "observe",
            recommendation=(
                "Review actionable novelty scopes before expanding exploration or search-term portfolio."
                if summary.actionable_novelty_scope_count
                else "No actionable novelty scope is currently visible in Gold summary."
            ),
            reason="Novelty and vocabulary learning should feed candidate/gate reassessment instead of isolated scripts.",
            metrics={
                "open_search_term_suggestion_count": summary.open_search_term_suggestion_count,
                "recent_company_vocabulary_observation_count": summary.recent_company_vocabulary_observation_count,
                "recent_unregistered_company_observation_count": summary.recent_unregistered_company_observation_count,
                "actionable_novelty_scope_count": summary.actionable_novelty_scope_count,
                "saturated_scope_count": summary.saturated_scope_count,
            },
        )
    )

    steps.append(
        OrchestratorStep(
            step_order=6,
            step_name="scheduler_boundary_review",
            step_status="deferred",
            action_mode="defer",
            recommendation="Keep scheduler integration deferred until this orchestrator has stable run history.",
            reason="The first foundation must be manually executable and audit-only; scheduler wiring is a later step.",
            metrics={"scheduler_change_allowed": False},
        )
    )

    attention_count = sum(1 for step in steps if step.step_status == "attention_required")
    blocked_count = sum(1 for step in steps if step.step_status == "blocked")
    status = "blocked" if blocked_count else ("completed_with_actions" if attention_count else "completed")

    return OrchestratorPlan(
        cycle_name="nightly_search_intelligence_cycle",
        status=status,
        steps=tuple(steps),
        summary={
            "step_count": len(steps),
            "attention_required_step_count": attention_count,
            "blocked_step_count": blocked_count,
            "approval_queue_count": approvals,
            "open_candidate_count": summary.open_candidate_count,
            "critical_fn_pressure_candidate_count": summary.critical_fn_pressure_candidate_count,
        },
        guardrails=dict(GUARDRAILS),
    )
