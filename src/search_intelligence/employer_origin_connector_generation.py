from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


ALLOWED_EMPLOYER_ORIGIN_SOURCE_TYPES = (
    "employer_origin_career_site",
    "employer_origin_ats_backed_career_site",
)

REQUIRED_GENERATION_GATES = (
    "company_candidate",
    "source_discovery",
    "risk_gate",
    "technical_reachability_gate",
    "scope_gate",
    "defensive_preview_gate",
    "relevance_gate",
    "detail_evidence_gate",
    "incremental_uniqueness_gate",
    "connector_candidate_gate",
)

CONNECTOR_CANDIDATE_GATE = "connector_candidate_gate"

GENERATION_BOUNDARY: dict[str, bool] = {
    "auto_pr_allowed": False,
    "connector_registration_allowed": False,
    "source_activation_allowed": False,
    "bronze_persistence_allowed": False,
    "recurring_ingestion_allowed": False,
    "scheduler_change_allowed": False,
    "csv_or_export_inputs_used": False,
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
    risk_level: str


@dataclass(frozen=True)
class GateReview:
    gate_name: str
    gate_status: str
    decision: str
    stop_reason: str | None
    evidence: dict[str, Any]


@dataclass(frozen=True)
class GateReassessmentSignal:
    status: str
    false_negative_risk_level: str
    priority: int
    trigger_reason: str
    suggested_search_terms: tuple[str, ...]
    updated_at: str | None
    latest_gate_reviewed_at: str | None = None


@dataclass(frozen=True)
class ConnectorGenerationPlan:
    candidate: SourceCandidate
    generation_status: str
    recommendation: str
    reason: str
    connector_module_path: str | None
    connector_test_path: str | None
    connector_docs_path: str | None
    next_command: str | None
    build_steps: tuple[dict[str, Any], ...]
    boundary: dict[str, bool]
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def snake_case(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", normalized).strip("_")


def default_connector_paths(candidate: SourceCandidate) -> dict[str, str]:
    module_name = snake_case(candidate.source_family_candidate)
    return {
        "module_path": f"src/connectors/{module_name}.py",
        "test_path": f"tests/test_{module_name}_connector.py",
        "docs_path": f"docs/planning/active/source-candidates/{module_name}_connector_candidate.md",
    }


def gate_summary(gates: dict[str, GateReview]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "gate_status": gate.gate_status,
            "decision": gate.decision,
            "stop_reason": gate.stop_reason,
        }
        for name, gate in sorted(gates.items())
    }


def missing_required_gates(gates: dict[str, GateReview]) -> list[str]:
    return [gate_name for gate_name in REQUIRED_GENERATION_GATES if gate_name not in gates]


def unpassed_required_gates(gates: dict[str, GateReview]) -> list[dict[str, str | None]]:
    result: list[dict[str, str | None]] = []
    for gate_name in REQUIRED_GENERATION_GATES:
        gate = gates.get(gate_name)
        if gate is None:
            continue
        if gate.gate_status != "passed":
            result.append(
                {
                    "gate_name": gate.gate_name,
                    "gate_status": gate.gate_status,
                    "decision": gate.decision,
                    "stop_reason": gate.stop_reason,
                }
            )
    return result


def connector_candidate_spec(gates: dict[str, GateReview]) -> dict[str, Any]:
    gate = gates.get(CONNECTOR_CANDIDATE_GATE)
    if gate is None:
        return {}

    spec = (gate.evidence or {}).get("connector_candidate_spec") or {}
    return spec if isinstance(spec, dict) else {}


def detail_urls_from_spec(spec: dict[str, Any]) -> tuple[str, ...]:
    detail_evidence = spec.get("detail_evidence") or {}
    urls = detail_evidence.get("detail_urls") or []
    return tuple(str(url) for url in urls if str(url).startswith(("http://", "https://")))


def recommended_paths(candidate: SourceCandidate, spec: dict[str, Any]) -> dict[str, str]:
    defaults = default_connector_paths(candidate)
    recommended = spec.get("recommended_connector") or {}
    return {
        "module_path": str(recommended.get("module_path") or defaults["module_path"]),
        "test_path": str(recommended.get("test_path") or defaults["test_path"]),
        "docs_path": str(recommended.get("docs_path") or defaults["docs_path"]),
    }


def generation_build_steps(
    *,
    candidate: SourceCandidate,
    paths: dict[str, str],
    reviewed_by: str,
    artifacts_exist: bool,
) -> tuple[dict[str, Any], ...]:
    generation_action = "review_existing_artifacts" if artifacts_exist else "dry_run_generation"
    generation_command = (
        f"python -m scripts.run_employer_origin_connector_artifact_generator "
        f"--company-key {candidate.company_key} --dry-run"
    )
    validation_command = (
        f"python -m scripts.run_employer_origin_connector_validation_agent "
        f"--company-key {candidate.company_key} --reviewed-by {reviewed_by}"
    )

    return (
        {
            "step": "discovery_candidate",
            "status": "covered_by_gate_state",
            "source": candidate.source_name_candidate,
        },
        {
            "step": "source_analysis",
            "status": "covered_by_gate_state",
            "required_gates": [
                "source_discovery",
                "risk_gate",
                "technical_reachability_gate",
                "scope_gate",
            ],
        },
        {
            "step": "connector_feasibility",
            "status": "covered_by_gate_state",
            "required_gates": [
                "defensive_preview_gate",
                "relevance_gate",
                "detail_evidence_gate",
                "incremental_uniqueness_gate",
                "connector_candidate_gate",
            ],
        },
        {
            "step": "connector_recommendation",
            "status": "ready",
            "module_path": paths["module_path"],
            "test_path": paths["test_path"],
            "docs_path": paths["docs_path"],
        },
        {
            "step": "build_plan",
            "status": generation_action,
            "command": validation_command if artifacts_exist else generation_command,
        },
        {
            "step": "review_and_validation",
            "status": "required_after_artifact_generation",
            "command": validation_command,
        },
        {
            "step": "explicit_approval_and_registration_plan",
            "status": "deferred",
            "approval_required": True,
            "activation_allowed_by_this_plan": False,
        },
    )


def _reassessment_signal_summary(signal: GateReassessmentSignal | None) -> dict[str, Any]:
    if signal is None:
        return {
            "status": "none",
            "gate_reassessment_required": False,
        }
    return {
        "status": signal.status,
        "gate_reassessment_required": signal.status == "open",
        "false_negative_risk_level": signal.false_negative_risk_level,
        "priority": signal.priority,
        "trigger_reason": signal.trigger_reason,
        "suggested_search_terms": list(signal.suggested_search_terms),
        "updated_at": signal.updated_at,
        "latest_gate_reviewed_at": signal.latest_gate_reviewed_at,
        "target_gates": [
            "detail_evidence_gate",
            "connector_candidate_gate",
        ],
    }


def _base_evidence(
    *,
    gates: dict[str, GateReview],
    spec: dict[str, Any],
    artifacts_exist: bool,
    reassessment_signal: GateReassessmentSignal | None = None,
) -> dict[str, Any]:
    detail_urls = detail_urls_from_spec(spec)
    return {
        "required_generation_gates": list(REQUIRED_GENERATION_GATES),
        "missing_required_gates": missing_required_gates(gates),
        "unpassed_required_gates": unpassed_required_gates(gates),
        "gate_state_summary": gate_summary(gates),
        "connector_candidate_spec_present": bool(spec),
        "detail_url_count": len(detail_urls),
        "detail_urls": list(detail_urls),
        "artifact_files_exist": artifacts_exist,
        "source_role": "origin_validation_ground_truth",
        "learning_reassessment_signal": _reassessment_signal_summary(reassessment_signal),
    }


def _plan(
    *,
    candidate: SourceCandidate,
    generation_status: str,
    recommendation: str,
    reason: str,
    paths: dict[str, str] | None,
    next_command: str | None,
    build_steps: tuple[dict[str, Any], ...],
    evidence: dict[str, Any],
) -> ConnectorGenerationPlan:
    return ConnectorGenerationPlan(
        candidate=candidate,
        generation_status=generation_status,
        recommendation=recommendation,
        reason=reason,
        connector_module_path=paths.get("module_path") if paths else None,
        connector_test_path=paths.get("test_path") if paths else None,
        connector_docs_path=paths.get("docs_path") if paths else None,
        next_command=next_command,
        build_steps=build_steps,
        boundary=dict(GENERATION_BOUNDARY),
        evidence=evidence,
    )


def build_connector_generation_plan(
    *,
    candidate: SourceCandidate,
    gates: dict[str, GateReview],
    artifacts_exist: bool = False,
    reviewed_by: str = "agent",
    reassessment_signal: GateReassessmentSignal | None = None,
) -> ConnectorGenerationPlan:
    spec = connector_candidate_spec(gates)
    paths = recommended_paths(candidate, spec)
    evidence = _base_evidence(
        gates=gates,
        spec=spec,
        artifacts_exist=artifacts_exist,
        reassessment_signal=reassessment_signal,
    )

    if candidate.status == "active_controlled":
        return _plan(
            candidate=candidate,
            generation_status="not_applicable",
            recommendation="monitor_existing_source",
            reason="candidate is already active_controlled",
            paths=paths,
            next_command=None,
            build_steps=(),
            evidence=evidence,
        )

    if candidate.source_type_candidate not in ALLOWED_EMPLOYER_ORIGIN_SOURCE_TYPES:
        return _plan(
            candidate=candidate,
            generation_status="blocked",
            recommendation="stop_before_connector_generation",
            reason="candidate source type is not an allowed employer-origin source type",
            paths=paths,
            next_command=None,
            build_steps=(),
            evidence=evidence,
        )

    if evidence["learning_reassessment_signal"]["gate_reassessment_required"]:
        return _plan(
            candidate=candidate,
            generation_status="gate_reassessment_required",
            recommendation="rerun_employer_origin_gate_reassessment",
            reason="new learning evidence requires gate state reassessment before connector generation",
            paths=paths,
            next_command=(
                "python -m scripts.run_employer_origin_agent_chain "
                f"--company-key {candidate.company_key} "
                f"--reviewed-by {reviewed_by} --attempt-repair"
            ),
            build_steps=(),
            evidence=evidence,
        )

    if evidence["missing_required_gates"]:
        return _plan(
            candidate=candidate,
            generation_status="manual_review_required",
            recommendation="stop_before_connector_generation",
            reason="required generation gates are missing",
            paths=paths,
            next_command=None,
            build_steps=(),
            evidence=evidence,
        )

    if evidence["unpassed_required_gates"]:
        return _plan(
            candidate=candidate,
            generation_status="manual_review_required",
            recommendation="stop_before_connector_generation",
            reason="required generation gates are not all passed",
            paths=paths,
            next_command=None,
            build_steps=(),
            evidence=evidence,
        )

    connector_gate = gates.get(CONNECTOR_CANDIDATE_GATE)
    if connector_gate is None or connector_gate.decision != "build_connector_candidate":
        return _plan(
            candidate=candidate,
            generation_status="manual_review_required",
            recommendation="stop_before_connector_generation",
            reason="connector_candidate_gate is not build_connector_candidate",
            paths=paths,
            next_command=None,
            build_steps=(),
            evidence=evidence,
        )

    if not spec:
        return _plan(
            candidate=candidate,
            generation_status="manual_review_required",
            recommendation="stop_before_connector_generation",
            reason="connector_candidate_spec is missing",
            paths=paths,
            next_command=None,
            build_steps=(),
            evidence=evidence,
        )

    if evidence["detail_url_count"] <= 0:
        return _plan(
            candidate=candidate,
            generation_status="manual_review_required",
            recommendation="stop_before_connector_generation",
            reason="connector_candidate_spec has no concrete detail URLs",
            paths=paths,
            next_command=None,
            build_steps=(),
            evidence=evidence,
        )

    steps = generation_build_steps(
        candidate=candidate,
        paths=paths,
        reviewed_by=reviewed_by,
        artifacts_exist=artifacts_exist,
    )
    next_command = str(steps[4]["command"])

    if artifacts_exist:
        return _plan(
            candidate=candidate,
            generation_status="already_generated",
            recommendation="review_existing_connector_artifacts",
            reason="connector artifact files already exist; move to validation instead of regenerating blindly",
            paths=paths,
            next_command=next_command,
            build_steps=steps,
            evidence=evidence,
        )

    return _plan(
        candidate=candidate,
        generation_status="ready",
        recommendation="prepare_connector_artifact_dry_run",
        reason="candidate has enough DB-backed gate evidence for bounded connector artifact generation planning",
        paths=paths,
        next_command=next_command,
        build_steps=steps,
        evidence=evidence,
    )
