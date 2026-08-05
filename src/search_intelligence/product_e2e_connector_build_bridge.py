"""Product E2E connector-build bridge contracts.

The bridge classifies existing S6C connector-build requests for a source-diverse
Golden-Path portfolio. Company identity is evidence only and never controls the
classification or persistence rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from src.search_intelligence.approval_gated_connector_build import (
    ConnectorBuildRequest,
)
from src.search_intelligence.origin_seed_pool import normalize_company_key

REQUEST_PERSISTENCE_APPROVAL_TOKEN = (
    "approve_product_e2e_connector_build_request_persistence"
)


@dataclass(frozen=True)
class ConnectorBuildBridgePlan:
    candidate_id: int
    company_key: str
    company_name: str
    discovery_source_class: str
    candidate_url: str
    build_status: str
    recommendation: str
    build_mode: str
    status: str
    reason_code: str
    reason: str
    approval_required: bool
    artifact_generation_allowed: bool
    request_persistence_allowed: bool
    next_command: str | None
    connector_module_path: str
    connector_test_path: str
    connector_docs_path: str
    queue_action: str | None
    queue_reason: str | None
    generation_status: str | None


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _queue_evidence(request: ConnectorBuildRequest) -> Mapping[str, object]:
    return _mapping(request.evidence.get("build_queue_evidence"))


def _generation_evidence(request: ConnectorBuildRequest) -> Mapping[str, object]:
    return _mapping(request.evidence.get("generation_plan"))


def classify_connector_build_request(
    request: ConnectorBuildRequest,
) -> tuple[str, str]:
    """Classify one existing S6C request without changing its authority."""

    build_status = request.build_status
    queue_action = _text(_queue_evidence(request).get("queue_action"))

    if build_status == "not_applicable":
        return "passed", "controlled_source_already_available"
    if build_status == "artifacts_present":
        return "passed", "connector_artifacts_present"
    if build_status == "build_approval_required":
        return "operator_decision_required", "connector_artifact_build_approval_required"
    if build_status == "artifact_generation_allowed":
        return "capability_gap", "unexpected_artifact_generation_authority_in_plan"
    if build_status == "gate_reassessment_required":
        return "valid_stop", "gate_reassessment_required_before_build"
    if build_status == "blocked":
        return "capability_gap", "connector_build_blocked"
    if build_status != "manual_review_required":
        return "capability_gap", "unclassified_connector_build_status"

    if queue_action == "origin_url_repair_required":
        return "valid_stop", "origin_url_repair_required_before_build"
    if queue_action == "origin_source_discovery_required":
        return "valid_stop", "origin_source_discovery_required_before_build"
    if queue_action == "sample_job_review_required":
        return "operator_decision_required", "sample_job_review_required_before_build"
    if queue_action == "manual_source_review_required":
        return "operator_decision_required", "manual_source_review_required_before_build"
    if queue_action == "monitor_or_manual_review":
        return "valid_stop", "connector_build_evidence_insufficient"
    return "capability_gap", "connector_build_evaluation_not_ready"


def build_connector_build_bridge_plan(
    *,
    discovery_source_class: str,
    request: ConnectorBuildRequest,
) -> ConnectorBuildBridgePlan:
    """Project one S6C request into a Product E2E portfolio outcome."""

    status, reason_code = classify_connector_build_request(request)
    queue = _queue_evidence(request)
    generation = _generation_evidence(request)
    persistence_allowed = bool(
        request.build_status == "build_approval_required"
        and request.approval_required
        and not request.approval_provided
        and not request.artifact_generation_allowed
    )
    return ConnectorBuildBridgePlan(
        candidate_id=request.candidate.candidate_id,
        company_key=normalize_company_key(request.candidate.company_key),
        company_name=request.candidate.company_name,
        discovery_source_class=discovery_source_class,
        candidate_url=request.candidate.candidate_url,
        build_status=request.build_status,
        recommendation=request.recommendation,
        build_mode=request.build_mode,
        status=status,
        reason_code=reason_code,
        reason=request.reason,
        approval_required=request.approval_required,
        artifact_generation_allowed=request.artifact_generation_allowed,
        request_persistence_allowed=persistence_allowed,
        next_command=request.next_command,
        connector_module_path=request.paths.module_path,
        connector_test_path=request.paths.test_path,
        connector_docs_path=request.paths.docs_path,
        queue_action=_text(queue.get("queue_action")),
        queue_reason=_text(queue.get("queue_reason")),
        generation_status=_text(generation.get("generation_status")),
    )


def parse_exact_target(value: str) -> tuple[int, str]:
    raw_id, separator, raw_key = value.partition(":")
    if not separator or not raw_id.isdigit():
        raise ValueError("Targets must use the exact format candidate_id:company_key.")
    company_key = normalize_company_key(raw_key)
    if not company_key:
        raise ValueError("Targets must include a non-empty canonical company_key.")
    return int(raw_id), company_key


def select_exact_target_plans(
    plans: Iterable[ConnectorBuildBridgePlan],
    *,
    requested_targets: Iterable[str],
    require_request_persistence: bool,
) -> tuple[ConnectorBuildBridgePlan, ...]:
    """Bind an exact target set to current DB-backed portfolio plans."""

    by_id = {plan.candidate_id: plan for plan in plans}
    selected: list[ConnectorBuildBridgePlan] = []
    selected_ids: set[int] = set()

    for raw_target in requested_targets:
        candidate_id, company_key = parse_exact_target(raw_target)
        if candidate_id in selected_ids:
            raise ValueError(f"Duplicate candidate target: {candidate_id}.")
        plan = by_id.get(candidate_id)
        if plan is None:
            raise ValueError(
                f"Candidate target {candidate_id}:{company_key} is not present in the "
                "current connector-build portfolio."
            )
        if plan.company_key != company_key:
            raise ValueError(
                f"Candidate target {candidate_id} has company_key={plan.company_key!r}, "
                f"not {company_key!r}."
            )
        if require_request_persistence and not plan.request_persistence_allowed:
            raise ValueError(
                f"Candidate target {candidate_id}:{company_key} is not eligible for "
                f"build-request persistence: {plan.reason_code}."
            )
        selected.append(plan)
        selected_ids.add(candidate_id)

    return tuple(selected)
