from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


EARLY_BUILD_GATE_NAMES = (
    "company_candidate",
    "source_discovery",
    "risk_gate",
    "technical_reachability_gate",
    "scope_gate",
    "defensive_preview_gate",
    "relevance_gate",
    "incremental_uniqueness_gate",
)

DETAIL_EVIDENCE_GATE = "detail_evidence_gate"
CONNECTOR_CANDIDATE_GATE = "connector_candidate_gate"
VALIDATION_GATE = "connector_validation_gate"
FINAL_APPROVAL_GATE = "final_approval_gate"

HIGH_FALSE_NEGATIVE_RISK_LEVELS = {"high", "critical"}
DETAIL_REPAIR_EXHAUSTED_MARKER = "bounded repair found no concrete detail pages"
ALLOWED_SOURCE_TYPES = {
    "employer_origin_career_site",
    "employer_origin_ats_backed_career_site",
}


@dataclass(frozen=True)
class SourceCandidate:
    candidate_id: int
    company_key: str
    company_name: str
    candidate_url: str
    source_name_candidate: str
    source_family_candidate: str
    source_target_candidate: str | None
    source_type_candidate: str
    status: str
    operational_risk_level: str


@dataclass(frozen=True)
class GateReview:
    gate_name: str
    gate_status: str
    decision: str
    stop_reason: str | None = None
    evidence: dict[str, Any] | None = None


@dataclass(frozen=True)
class GenerationPlanState:
    generation_status: str | None
    recommendation: str | None
    updated_at: str | None = None
    evidence: dict[str, Any] | None = None


@dataclass(frozen=True)
class LearningPressure:
    status: str
    false_negative_risk_level: str
    priority: int
    trigger_reason: str
    suggested_search_terms: tuple[str, ...]
    updated_at: str | None = None


@dataclass(frozen=True)
class BuildQueueEvidence:
    candidate_id: int
    queue_action: str
    queue_reason: str | None
    recommended_command_or_review: str | None
    feasibility_status: str | None
    feasibility_decision: str | None
    url_quality_status: str | None
    job_detail_candidate_evidence_count: int
    structural_job_evidence_count: int
    review_created_at: str | None = None
    candidate_url: str | None = None
    page_type: str | None = None
    sample_job_count: int = 0
    sample_job_urls: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorPaths:
    module_path: str
    test_path: str
    docs_path: str


@dataclass(frozen=True)
class ConnectorBuildRequest:
    candidate: SourceCandidate
    build_status: str
    recommendation: str
    reason: str
    build_mode: str
    approval_required: bool
    approval_provided: bool
    artifact_generation_allowed: bool
    next_command: str | None
    paths: ConnectorPaths
    boundary: dict[str, Any]
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate": {
                "candidate_id": self.candidate.candidate_id,
                "company_key": self.candidate.company_key,
                "company_name": self.candidate.company_name,
                "source_name_candidate": self.candidate.source_name_candidate,
                "source_type_candidate": self.candidate.source_type_candidate,
                "status": self.candidate.status,
                "operational_risk_level": self.candidate.operational_risk_level,
            },
            "build_status": self.build_status,
            "recommendation": self.recommendation,
            "reason": self.reason,
            "build_mode": self.build_mode,
            "approval_required": self.approval_required,
            "approval_provided": self.approval_provided,
            "artifact_generation_allowed": self.artifact_generation_allowed,
            "next_command": self.next_command,
            "paths": {
                "module_path": self.paths.module_path,
                "test_path": self.paths.test_path,
                "docs_path": self.paths.docs_path,
            },
            "boundary": self.boundary,
            "evidence": self.evidence,
        }


def snake_case(value: str) -> str:
    import re

    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", normalized).strip("_")


def default_connector_paths(candidate: SourceCandidate) -> ConnectorPaths:
    module_name = snake_case(candidate.source_family_candidate or candidate.company_key)
    return ConnectorPaths(
        module_path=f"src/connectors/{module_name}.py",
        test_path=f"tests/test_{module_name}_connector.py",
        docs_path=f"docs/source_analysis/{module_name}_connector_candidate.md",
    )


def gate_passed(gates: dict[str, GateReview], gate_name: str) -> bool:
    gate = gates.get(gate_name)
    return bool(gate and gate.gate_status == "passed")


def gate_decision(gates: dict[str, GateReview], gate_name: str) -> str | None:
    gate = gates.get(gate_name)
    return gate.decision if gate else None


def early_build_gates_passed(gates: dict[str, GateReview]) -> bool:
    return all(gate_passed(gates, gate_name) for gate_name in EARLY_BUILD_GATE_NAMES)


def missing_early_build_gates(gates: dict[str, GateReview]) -> tuple[str, ...]:
    return tuple(gate_name for gate_name in EARLY_BUILD_GATE_NAMES if gate_name not in gates)


def unpassed_early_build_gates(gates: dict[str, GateReview]) -> tuple[dict[str, Any], ...]:
    result: list[dict[str, Any]] = []
    for gate_name in EARLY_BUILD_GATE_NAMES:
        gate = gates.get(gate_name)
        if gate is None or gate.gate_status == "passed":
            continue
        result.append(
            {
                "gate_name": gate_name,
                "gate_status": gate.gate_status,
                "decision": gate.decision,
                "stop_reason": gate.stop_reason,
            }
        )
    return tuple(result)


def connector_candidate_gate_ready(gates: dict[str, GateReview]) -> bool:
    return gate_passed(gates, CONNECTOR_CANDIDATE_GATE) and gate_decision(gates, CONNECTOR_CANDIDATE_GATE) == "build_connector_candidate"


def connector_validation_ready(gates: dict[str, GateReview]) -> bool:
    return gate_passed(gates, VALIDATION_GATE) and gate_decision(gates, VALIDATION_GATE) == "ready_for_final_approval"


def final_approval_passed(gates: dict[str, GateReview]) -> bool:
    return gate_passed(gates, FINAL_APPROVAL_GATE) and gate_decision(gates, FINAL_APPROVAL_GATE) == "approve_connector_registration"


def high_false_negative_pressure(pressure: LearningPressure | None) -> bool:
    return bool(pressure and pressure.status == "open" and pressure.false_negative_risk_level in HIGH_FALSE_NEGATIVE_RISK_LEVELS)


BUILD_QUEUE_CONNECTOR_BUILD_ACTIONS = {
    "build_candidate_recommended",
    "continue_existing_build_flow",
}


def build_queue_recommends_connector_build(queue: BuildQueueEvidence | None) -> bool:
    return bool(
        queue
        and queue.queue_action in BUILD_QUEUE_CONNECTOR_BUILD_ACTIONS
        and queue.feasibility_status == "likely_feasible"
        and queue.feasibility_decision == "continue_to_connector_build_planning"
        and queue.url_quality_status == "valid_probe_ready"
        and queue.job_detail_candidate_evidence_count > 0
    )


def detail_evidence_repair_exhausted(gates: dict[str, GateReview]) -> bool:
    gate = gates.get(DETAIL_EVIDENCE_GATE)
    if not gate or gate.gate_status != "manual_review_required":
        return False
    return DETAIL_REPAIR_EXHAUSTED_MARKER in (gate.stop_reason or "")


def generation_plan_ready(plan: GenerationPlanState | None) -> bool:
    if plan is None:
        return False
    return plan.generation_status in {"ready", "already_generated"} and plan.recommendation in {
        "prepare_connector_artifact_dry_run",
        "review_existing_connector_artifacts",
    }


def gate_reassessment_required(plan: GenerationPlanState | None) -> bool:
    if plan is None:
        return False
    return plan.generation_status == "gate_reassessment_required" or plan.recommendation == "rerun_employer_origin_gate_reassessment"


def connector_candidate_spec(gates: dict[str, GateReview]) -> dict[str, Any]:
    gate = gates.get(CONNECTOR_CANDIDATE_GATE)
    if not gate:
        return {}
    evidence = gate.evidence or {}
    spec = evidence.get("connector_candidate_spec") or {}
    return spec if isinstance(spec, dict) else {}


def build_boundary(*, approval_provided: bool) -> dict[str, Any]:
    return {
        "connector_artifact_generation_allowed_after_explicit_approval": approval_provided,
        "connector_registration_allowed": False,
        "source_activation_allowed": False,
        "bronze_persistence_allowed": False,
        "recurring_ingestion_allowed": False,
        "scheduler_change_allowed": False,
        "auto_pr_allowed": False,
        "csv_or_export_inputs_used": False,
    }


def build_next_command(candidate: SourceCandidate, *, reviewed_by: str, approve: bool = False) -> str:
    token = " --approve-build" if approve else ""
    return (
        "python -m scripts.run_approval_gated_connector_build_agent "
        f"--company-key {candidate.company_key} --reviewed-by {reviewed_by}{token} --write"
    )


def evaluate_connector_build_request(
    *,
    candidate: SourceCandidate,
    gates: dict[str, GateReview],
    generation_plan: GenerationPlanState | None,
    learning_pressure: LearningPressure | None,
    artifact_files_exist: bool,
    approval_provided: bool,
    reviewed_by: str,
    build_queue_evidence: BuildQueueEvidence | None = None,
) -> ConnectorBuildRequest:
    paths = default_connector_paths(candidate)
    boundary = build_boundary(approval_provided=approval_provided)
    evidence: dict[str, Any] = {
        "agent": "s6c_approval_gated_connector_build_agent",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_type_allowed": candidate.source_type_candidate in ALLOWED_SOURCE_TYPES,
        "missing_early_build_gates": list(missing_early_build_gates(gates)),
        "unpassed_early_build_gates": list(unpassed_early_build_gates(gates)),
        "early_build_gates_passed": early_build_gates_passed(gates),
        "detail_evidence_gate": _gate_summary(gates.get(DETAIL_EVIDENCE_GATE)),
        "detail_evidence_repair_exhausted": detail_evidence_repair_exhausted(gates),
        "connector_candidate_gate": _gate_summary(gates.get(CONNECTOR_CANDIDATE_GATE)),
        "connector_candidate_spec_present": bool(connector_candidate_spec(gates)),
        "connector_validation_ready": connector_validation_ready(gates),
        "final_approval_passed": final_approval_passed(gates),
        "generation_plan": _generation_plan_summary(generation_plan),
        "learning_pressure": _learning_pressure_summary(learning_pressure),
        "build_queue_evidence": _build_queue_evidence_summary(build_queue_evidence),
        "artifact_files_exist": artifact_files_exist,
    }

    if candidate.status == "active_controlled":
        return _request(
            candidate=candidate,
            paths=paths,
            build_status="not_applicable",
            recommendation="monitor_existing_source",
            reason="candidate is already active_controlled",
            build_mode="none",
            approval_required=False,
            approval_provided=approval_provided,
            artifact_generation_allowed=False,
            next_command=None,
            boundary=boundary,
            evidence=evidence,
        )

    if candidate.source_type_candidate not in ALLOWED_SOURCE_TYPES:
        return _request(
            candidate=candidate,
            paths=paths,
            build_status="blocked",
            recommendation="stop_before_build",
            reason="candidate source type is not allowed for employer-origin connector build",
            build_mode="none",
            approval_required=False,
            approval_provided=approval_provided,
            artifact_generation_allowed=False,
            next_command=None,
            boundary=boundary,
            evidence=evidence,
        )

    if gate_reassessment_required(generation_plan):
        if (
            early_build_gates_passed(gates)
            and high_false_negative_pressure(learning_pressure)
            and detail_evidence_repair_exhausted(gates)
        ):
            return _approval_request(
                candidate=candidate,
                paths=paths,
                reason=(
                    "gate reassessment still blocks detail evidence, but high false-negative pressure "
                    "and exhausted bounded detail repair justify an explicitly approved investigation build"
                ),
                build_mode="bounded_investigation_connector",
                approval_provided=approval_provided,
                reviewed_by=reviewed_by,
                boundary=boundary,
                evidence=evidence,
            )
        return _request(
            candidate=candidate,
            paths=paths,
            build_status="gate_reassessment_required",
            recommendation="rerun_employer_origin_gate_reassessment",
            reason="connector-generation plan requires gate reassessment before artifact build",
            build_mode="none",
            approval_required=False,
            approval_provided=approval_provided,
            artifact_generation_allowed=False,
            next_command=(
                "python -m scripts.run_employer_origin_agent_chain "
                f"--company-key {candidate.company_key} --reviewed-by {reviewed_by} --attempt-repair"
            ),
            boundary=boundary,
            evidence=evidence,
        )

    if artifact_files_exist:
        return _request(
            candidate=candidate,
            paths=paths,
            build_status="artifacts_present",
            recommendation="run_connector_validation",
            reason="connector artifact files already exist; validate before registration approval",
            build_mode="existing_artifacts",
            approval_required=False,
            approval_provided=approval_provided,
            artifact_generation_allowed=False,
            next_command=(
                "python -m scripts.run_employer_origin_connector_validation_agent "
                f"--company-key {candidate.company_key}"
            ),
            boundary=boundary,
            evidence=evidence,
        )

    if generation_plan_ready(generation_plan) or connector_candidate_gate_ready(gates):
        return _approval_request(
            candidate=candidate,
            paths=paths,
            reason="connector-generation gates are ready for a bounded artifact dry run",
            build_mode="connector_candidate_from_gate_evidence",
            approval_provided=approval_provided,
            reviewed_by=reviewed_by,
            boundary=boundary,
            evidence=evidence,
        )

    if build_queue_recommends_connector_build(build_queue_evidence):
        return _approval_request(
            candidate=candidate,
            paths=paths,
            reason=(
                "S7O build candidate queue recommends or continues connector build planning based on latest "
                "reachable origin-source and concrete job-detail evidence"
            ),
            build_mode="connector_candidate_from_build_queue_evidence",
            approval_provided=approval_provided,
            reviewed_by=reviewed_by,
            boundary=boundary,
            evidence=evidence,
        )

    # Controlled escape hatch: high market/false-negative pressure may justify building a bounded
    # investigation connector artifact even when concrete detail evidence was not found yet.
    # Registration and activation remain impossible until validation and final approval pass later.
    if early_build_gates_passed(gates) and high_false_negative_pressure(learning_pressure):
        return _approval_request(
            candidate=candidate,
            paths=paths,
            reason=(
                "high false-negative pressure and passed early gates justify a bounded investigation "
                "connector build, but not registration or activation"
            ),
            build_mode="bounded_investigation_connector",
            approval_provided=approval_provided,
            reviewed_by=reviewed_by,
            boundary=boundary,
            evidence=evidence,
        )

    return _request(
        candidate=candidate,
        paths=paths,
        build_status="manual_review_required",
        recommendation="stop_before_build",
        reason="neither connector-generation gates nor high-pressure investigation-build criteria are satisfied",
        build_mode="none",
        approval_required=False,
        approval_provided=approval_provided,
        artifact_generation_allowed=False,
        next_command=None,
        boundary=boundary,
        evidence=evidence,
    )


def _approval_request(
    *,
    candidate: SourceCandidate,
    paths: ConnectorPaths,
    reason: str,
    build_mode: str,
    approval_provided: bool,
    reviewed_by: str,
    boundary: dict[str, Any],
    evidence: dict[str, Any],
) -> ConnectorBuildRequest:
    if approval_provided:
        return _request(
            candidate=candidate,
            paths=paths,
            build_status="artifact_generation_allowed",
            recommendation="generate_connector_artifacts",
            reason=reason,
            build_mode=build_mode,
            approval_required=True,
            approval_provided=True,
            artifact_generation_allowed=True,
            next_command=None,
            boundary=boundary,
            evidence=evidence,
        )

    return _request(
        candidate=candidate,
        paths=paths,
        build_status="build_approval_required",
        recommendation="request_explicit_build_approval",
        reason=reason,
        build_mode=build_mode,
        approval_required=True,
        approval_provided=False,
        artifact_generation_allowed=False,
        next_command=build_next_command(candidate, reviewed_by=reviewed_by, approve=True),
        boundary=boundary,
        evidence=evidence,
    )


def _request(
    *,
    candidate: SourceCandidate,
    paths: ConnectorPaths,
    build_status: str,
    recommendation: str,
    reason: str,
    build_mode: str,
    approval_required: bool,
    approval_provided: bool,
    artifact_generation_allowed: bool,
    next_command: str | None,
    boundary: dict[str, Any],
    evidence: dict[str, Any],
) -> ConnectorBuildRequest:
    return ConnectorBuildRequest(
        candidate=candidate,
        build_status=build_status,
        recommendation=recommendation,
        reason=reason,
        build_mode=build_mode,
        approval_required=approval_required,
        approval_provided=approval_provided,
        artifact_generation_allowed=artifact_generation_allowed,
        next_command=next_command,
        paths=paths,
        boundary=boundary,
        evidence=evidence,
    )


def _gate_summary(gate: GateReview | None) -> dict[str, Any]:
    if gate is None:
        return {"present": False}
    return {
        "present": True,
        "gate_status": gate.gate_status,
        "decision": gate.decision,
        "stop_reason": gate.stop_reason,
    }


def _generation_plan_summary(plan: GenerationPlanState | None) -> dict[str, Any]:
    if plan is None:
        return {"present": False}
    return {
        "present": True,
        "generation_status": plan.generation_status,
        "recommendation": plan.recommendation,
        "updated_at": plan.updated_at,
    }


def _learning_pressure_summary(pressure: LearningPressure | None) -> dict[str, Any]:
    if pressure is None:
        return {"present": False}
    return {
        "present": True,
        "status": pressure.status,
        "false_negative_risk_level": pressure.false_negative_risk_level,
        "priority": pressure.priority,
        "trigger_reason": pressure.trigger_reason,
        "suggested_search_terms": list(pressure.suggested_search_terms),
        "updated_at": pressure.updated_at,
    }


def _build_queue_evidence_summary(queue: BuildQueueEvidence | None) -> dict[str, Any]:
    if queue is None:
        return {"present": False}
    return {
        "present": True,
        "queue_action": queue.queue_action,
        "queue_reason": queue.queue_reason,
        "recommended_command_or_review": queue.recommended_command_or_review,
        "feasibility_status": queue.feasibility_status,
        "feasibility_decision": queue.feasibility_decision,
        "url_quality_status": queue.url_quality_status,
        "job_detail_candidate_evidence_count": queue.job_detail_candidate_evidence_count,
        "structural_job_evidence_count": queue.structural_job_evidence_count,
        "review_created_at": queue.review_created_at,
        "candidate_url": queue.candidate_url,
        "page_type": queue.page_type,
        "sample_job_count": queue.sample_job_count,
        "sample_job_urls": list(queue.sample_job_urls),
    }
