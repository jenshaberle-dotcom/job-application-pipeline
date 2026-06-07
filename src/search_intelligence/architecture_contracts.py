from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class SafetyZone:
    id: str
    level: int
    name: str
    allowed_writes: tuple[str, ...]
    required_control: str
    audit_required: bool


@dataclass(frozen=True)
class AgentPermission:
    agent: str
    safety_zone: str
    may_read: tuple[str, ...]
    may_write: tuple[str, ...]
    may_call_external_network: bool
    may_activate_source: bool
    may_delete_or_disable: bool
    required_control: str


@dataclass(frozen=True)
class LifecycleState:
    domain: str
    state: str
    allowed_next_states: tuple[str, ...]
    automatic_transition_allowed: bool
    audit_required: bool


SAFETY_ZONES: Final[tuple[SafetyZone, ...]] = (
    SafetyZone("SZ0_READ_ONLY", 0, "Read-only analysis and reporting", ("exports", "logs"), "default allowed; no database mutation", False),
    SafetyZone("SZ1_CANDIDATE_METADATA", 1, "Candidate metadata write", ("candidate_url", "candidate_status", "candidate_notes"), "dry-run first plus explicit --apply", True),
    SafetyZone("SZ2_EVIDENCE_AND_GATES", 2, "Evidence and gate event write", ("evidence_rows", "gate_events", "gate_reviews"), "dry-run first plus explicit --apply plus gate contract", True),
    SafetyZone("SZ3_CONNECTOR_ARTIFACTS", 3, "Connector artifact generation", ("connector_artifacts", "review_exports"), "approval-required state; no registration side effect", True),
    SafetyZone("SZ4_SOURCE_ACTIVATION", 4, "Source registration and activation", ("source_registry", "active_profiles", "activation_events"), "manual approval gate only", True),
    SafetyZone("SZ5_SCHEDULED_AUTOMATION", 5, "Scheduled production execution", ("scheduled_run_state", "orchestrator_steps", "run_results"), "bounded schedule policy plus previous stage maturity evidence", True),
    SafetyZone("SZ6_DESTRUCTIVE_OR_COMPLIANCE", 6, "Destructive, disabling, cleanup or compliance operation", ("disable_markers", "removal_events", "cleanup_events"), "dry-run inventory plus explicit apply plus protected-target override", True),
)


AGENT_PERMISSIONS: Final[tuple[AgentPermission, ...]] = (
    AgentPermission("market_sensor", "SZ0_READ_ONLY", ("external_job_search_results", "known_candidates"), ("exports", "raw_observation_candidates_when_ingestion_runner_allows"), True, False, False, "bounded connector/search-provider policy"),
    AgentPermission("candidate_promotion_tuersteher", "SZ1_CANDIDATE_METADATA", ("market_sensor_outputs", "existing_candidates", "candidate_history"), ("candidate_metadata", "promotion_recommendations"), False, False, False, "dry-run first for bulk promotion; explicit reason per candidate"),
    AgentPermission("origin_url_finder", "SZ0_READ_ONLY", ("candidate_metadata", "market_evidence", "offline_search_results"), ("exports", "validation_reports"), True, False, False, "bounded HTTP probing; no candidate_url write in validation mode"),
    AgentPermission("origin_url_recovery_writer", "SZ1_CANDIDATE_METADATA", ("url_finder_reports", "candidate_metadata"), ("candidate_url", "candidate_review_state"), False, False, False, "dry-run first plus explicit --apply plus selected_url evidence"),
    AgentPermission("detail_evidence_agent", "SZ2_EVIDENCE_AND_GATES", ("candidate_url", "origin_source_pages", "market_evidence"), ("detail_evidence", "gate_events"), True, False, False, "bounded page budget; gate contract output required"),
    AgentPermission("connector_build_agent", "SZ3_CONNECTOR_ARTIFACTS", ("validated_origin_source", "detail_evidence", "gate_reviews"), ("connector_artifacts", "review_exports"), False, False, False, "approval-required state; generated artifacts are review candidates only"),
    AgentPermission("approval_ui_or_operator", "SZ4_SOURCE_ACTIVATION", ("candidate_lifecycle", "evidence", "gate_reviews", "connector_artifacts"), ("approval_events", "source_activation"), False, True, False, "explicit human approval and audit event"),
    AgentPermission("scheduler_orchestrator", "SZ5_SCHEDULED_AUTOMATION", ("active_profiles", "source_health", "wave_plan"), ("orchestrator_runs", "orchestrator_steps", "scheduled_run_results"), True, False, False, "bounded wave plan and disabled-by-default write escalation"),
    AgentPermission("cleanup_or_compliance_agent", "SZ6_DESTRUCTIVE_OR_COMPLIANCE", ("all_candidate_and_source_state",), ("disable_markers", "cleanup_events", "removal_events"), False, False, True, "dry-run inventory plus explicit protected-target override"),
)


CANDIDATE_LIFECYCLE_STATES: Final[tuple[LifecycleState, ...]] = (
    LifecycleState("candidate", "discovered", ("promotion_recommended", "rejected_or_parked"), True, True),
    LifecycleState("candidate", "promotion_recommended", ("origin_url_required", "manual_review_required", "rejected_or_parked"), False, True),
    LifecycleState("candidate", "origin_url_required", ("origin_url_candidate_found", "manual_review_required"), True, True),
    LifecycleState("candidate", "origin_url_candidate_found", ("origin_url_validated", "manual_review_required"), False, True),
    LifecycleState("candidate", "origin_url_validated", ("detail_evidence_required", "connector_candidate"), False, True),
    LifecycleState("candidate", "detail_evidence_required", ("detail_evidence_found", "manual_review_required"), True, True),
    LifecycleState("candidate", "detail_evidence_found", ("connector_candidate", "manual_review_required"), False, True),
    LifecycleState("candidate", "connector_candidate", ("build_approval_required", "manual_review_required"), False, True),
    LifecycleState("candidate", "build_approval_required", ("connector_artifact_generated", "manual_review_required"), False, True),
    LifecycleState("candidate", "connector_artifact_generated", ("validation_required", "manual_review_required"), False, True),
    LifecycleState("candidate", "validation_required", ("approval_required", "manual_review_required"), False, True),
    LifecycleState("candidate", "approval_required", ("active_controlled", "manual_review_required"), False, True),
    LifecycleState("candidate", "active_controlled", ("monitor", "deactivation_review_required"), False, True),
    LifecycleState("candidate", "manual_review_required", ("origin_url_required", "detail_evidence_required", "connector_candidate", "rejected_or_parked"), False, True),
    LifecycleState("candidate", "rejected_or_parked", ("manual_review_required",), False, True),
)


GATE_CONTRACT_REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "gate_name", "candidate_id", "input_evidence_refs", "decision", "decision_confidence", "risk_level", "stop_reason", "next_safe_action", "manual_override_path", "audit_event_ref",
)


SECURITY_BASELINE_CONTROLS: Final[tuple[str, ...]] = (
    "block_private_ip_and_localhost_targets", "block_cloud_metadata_endpoints", "bound_http_connect_and_read_timeouts", "bound_total_candidate_runtime", "limit_redirect_depth_and_revalidate_final_host", "limit_response_size_for_probe_context", "never_write_secrets_to_exports_or_reports", "keep_provider_api_keys_in_environment_or_secret_store", "separate_read_only_validation_from_write_apply_modes", "log_rejected_network_targets_with_reason",
)


MATURITY_TARGETS_90_PLUS: Final[dict[str, int]] = {
    "architecture_contract": 90,
    "safety_model": 90,
    "security_model": 90,
    "agent_permissions": 90,
    "pipeline_state_machine": 90,
    "gate_contracts": 90,
    "diagnosis_observability": 90,
    "operational_generics": 90,
}


def validate_architecture_contracts() -> list[str]:
    violations: list[str] = []
    zone_ids = {zone.id for zone in SAFETY_ZONES}
    if len(zone_ids) != len(SAFETY_ZONES):
        violations.append("Safety zone IDs must be unique.")
    levels = [zone.level for zone in SAFETY_ZONES]
    if levels != sorted(levels):
        violations.append("Safety zones must be ordered by ascending level.")
    for permission in AGENT_PERMISSIONS:
        if permission.safety_zone not in zone_ids:
            violations.append(f"Agent {permission.agent} references unknown safety zone {permission.safety_zone}.")
        if permission.may_activate_source and permission.safety_zone != "SZ4_SOURCE_ACTIVATION":
            violations.append(f"Agent {permission.agent} may activate sources outside SZ4.")
        if permission.may_delete_or_disable and permission.safety_zone != "SZ6_DESTRUCTIVE_OR_COMPLIANCE":
            violations.append(f"Agent {permission.agent} may delete/disable outside SZ6.")
    states = {state.state for state in CANDIDATE_LIFECYCLE_STATES}
    for state in CANDIDATE_LIFECYCLE_STATES:
        for next_state in state.allowed_next_states:
            if next_state not in states and next_state not in {"monitor", "deactivation_review_required"}:
                violations.append(f"State {state.state} references unknown next state {next_state}.")
        if state.automatic_transition_allowed and not state.audit_required:
            violations.append(f"Automatic state {state.state} must require audit.")
    if len(GATE_CONTRACT_REQUIRED_FIELDS) < 8:
        violations.append("Gate contract must define enough required fields for explainability.")
    if "block_private_ip_and_localhost_targets" not in SECURITY_BASELINE_CONTROLS:
        violations.append("Security baseline must include private IP / localhost blocking.")
    if "bound_total_candidate_runtime" not in SECURITY_BASELINE_CONTROLS:
        violations.append("Security baseline must include total candidate runtime budget.")
    return violations
