from __future__ import annotations

from pathlib import Path

from src.search_intelligence.architecture_contracts import (
    AGENT_PERMISSIONS,
    CANDIDATE_LIFECYCLE_STATES,
    GATE_CONTRACT_REQUIRED_FIELDS,
    SAFETY_ZONES,
    SECURITY_BASELINE_CONTROLS,
    validate_architecture_contracts,
)


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_architecture_contracts_validate() -> None:
    assert validate_architecture_contracts() == []


def test_safety_zones_cover_write_escalation_path() -> None:
    zone_ids = [zone.id for zone in SAFETY_ZONES]
    assert zone_ids == [
        "SZ0_READ_ONLY",
        "SZ1_CANDIDATE_METADATA",
        "SZ2_EVIDENCE_AND_GATES",
        "SZ3_CONNECTOR_ARTIFACTS",
        "SZ4_SOURCE_ACTIVATION",
        "SZ5_SCHEDULED_AUTOMATION",
        "SZ6_DESTRUCTIVE_OR_COMPLIANCE",
    ]
    assert all(zone.required_control for zone in SAFETY_ZONES)


def test_agent_permissions_protect_activation_and_cleanup() -> None:
    activating_agents = [permission.agent for permission in AGENT_PERMISSIONS if permission.may_activate_source]
    destructive_agents = [permission.agent for permission in AGENT_PERMISSIONS if permission.may_delete_or_disable]
    assert activating_agents == ["approval_ui_or_operator"]
    assert destructive_agents == ["cleanup_or_compliance_agent"]


def test_security_baseline_contains_network_boundary_controls() -> None:
    assert "block_private_ip_and_localhost_targets" in SECURITY_BASELINE_CONTROLS
    assert "block_cloud_metadata_endpoints" in SECURITY_BASELINE_CONTROLS
    assert "bound_total_candidate_runtime" in SECURITY_BASELINE_CONTROLS
    assert "never_write_secrets_to_exports_or_reports" in SECURITY_BASELINE_CONTROLS


def test_candidate_state_machine_has_manual_and_active_boundaries() -> None:
    states = {state.state: state for state in CANDIDATE_LIFECYCLE_STATES}
    assert "manual_review_required" in states
    assert "active_controlled" in states
    assert states["approval_required"].automatic_transition_allowed is False
    assert "active_controlled" in states["approval_required"].allowed_next_states


def test_gate_contract_requires_diagnosis_fields() -> None:
    required = set(GATE_CONTRACT_REQUIRED_FIELDS)
    assert {"stop_reason", "next_safe_action", "manual_override_path", "audit_event_ref"}.issubset(required)


def test_arch001_documents_exist_and_name_freeze_scope() -> None:
    docs = [
        "docs/reference/security/safety_security_state_architecture.md",
        "docs/reference/agents/agent_permission_matrix.md",
        "docs/current/pipeline.md",
        "docs/reference/scoring-and-gates/gate_contract_baseline.md",
        "docs/reference/security/search_intelligence_security_baseline.md",
        "docs/archive/planning/architecture_freeze_maturity_campaign.md",
        "docs/decisions/adr/033_define_search_intelligence_safety_security_boundaries.md",
    ]
    for doc in docs:
        text = read(doc)
        assert "Status:" in text or "Status: Accepted" in text
    campaign = read("docs/archive/planning/architecture_freeze_maturity_campaign.md")
    assert "15 to 20 points" in campaign
    assert "White-Whale" in campaign


def test_security_doc_mentions_ssrf_relevant_boundaries() -> None:
    text = read("docs/reference/security/search_intelligence_security_baseline.md")
    assert "localhost" in text
    assert "private IP" in text
    assert "metadata" in text
    assert "secrets" in text


def test_readme_and_roadmap_have_arch001_markers() -> None:
    assert "ARCH-001-SAFETY-SECURITY-STATE" in read("README.md")
    assert "ARCH-001-SAFETY-SECURITY-STATE" in read("docs/planning/active/roadmap.md")
    assert "ARCH-001-SAFETY-SECURITY-STATE" in read("docs/reference/search-intelligence/current_state.md")
