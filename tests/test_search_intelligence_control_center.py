from __future__ import annotations

from scripts.search_intelligence_control_center import (
    BUILD_APPROVAL_TOKEN,
    REGISTRATION_APPROVAL_TOKEN,
    ControlCenterCandidate,
    build_approval_command,
    registration_approval_command,
    render_control_center,
)


def candidate(**overrides: object) -> ControlCenterCandidate:
    data = dict(
        candidate_id=2,
        company_key="hdi",
        company_name="HDI Group",
        candidate_url="https://careers.hdi.group/en/your_career_opportunities/job_board",
        source_name_candidate="hdi:hannover",
        source_type_candidate="employer_origin_career_site",
        status="manual_review_required",
        operational_risk_level="low",
        false_negative_risk_level="critical",
        reassessment_status="open",
        reassessment_reason="unresolved employer-origin candidate has five or more recent aggregator sightings",
        generation_status="gate_reassessment_required",
        generation_recommendation="rerun_employer_origin_gate_reassessment",
        build_status="build_approval_required",
        build_recommendation="request_explicit_build_approval",
        build_mode="bounded_investigation_connector",
        build_next_command="python -m scripts.run_approval_gated_connector_build_agent --company-key hdi --reviewed-by jens --approve-build --write",
        connector_module_path="src/connectors/hdi.py",
        connector_test_path="tests/test_hdi_connector.py",
        connector_docs_path="docs/source_analysis/hdi_connector_candidate.md",
        gate_passed_count=8,
        gate_manual_review_count=2,
        gate_blocked_count=0,
        gate_total_count=14,
        latest_blocking_gate="detail_evidence_gate",
        latest_blocking_reason="bounded repair found no concrete detail pages with profile and target/remote signals",
        connector_validation_status=None,
        connector_validation_decision=None,
        final_approval_status=None,
        final_approval_decision=None,
    )
    data.update(overrides)
    return ControlCenterCandidate(**data)


def test_control_center_renders_active_connectors_candidates_and_build_approvals() -> None:
    html = render_control_center(
        [
            candidate(),
            candidate(
                candidate_id=1,
                company_key="finanz_informatik",
                company_name="Finanz Informatik GmbH & Co. KG",
                source_name_candidate="finanz_informatik:hannover",
                status="active_controlled",
                false_negative_risk_level=None,
                reassessment_status=None,
                build_status=None,
                build_recommendation=None,
                latest_blocking_gate=None,
                latest_blocking_reason=None,
                gate_passed_count=14,
                gate_manual_review_count=0,
                gate_total_count=14,
            ),
        ],
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=False,
    )

    assert "Search Intelligence Control Center" in html
    assert "Active Connectors" in html
    assert "Finanz Informatik GmbH" in html
    assert "Connector Build & Registration Approvals" in html
    assert "HDI Group" in html
    assert BUILD_APPROVAL_TOKEN in html
    assert "Discovery → Candidate → Origin Exploration → Connector → Approval" in html
    assert "Start the UI with" in html
    assert "Stop UI" in html
    assert "/actions/shutdown" in html
    assert html.count("<nav class='top-nav'>") == 1
    assert "dashboard-grid" in html
    assert "Show approval command" in html


def test_control_center_renders_registration_approval_after_validation() -> None:
    html = render_control_center(
        [
            candidate(
                build_status="artifacts_present",
                build_recommendation="run_connector_validation",
                connector_validation_status="passed",
                connector_validation_decision="ready_for_final_approval",
                final_approval_status="manual_review_required",
                final_approval_decision="manual_review_required",
            )
        ],
        reviewed_by="jens",
        target_location="hannover",
        write_actions_enabled=True,
    )

    assert "Registration approval" in html
    assert REGISTRATION_APPROVAL_TOKEN in html
    assert "approve-registration" in html


def test_build_approval_command_is_bounded_to_s6c_build_only() -> None:
    command = build_approval_command("hdi", "jens")

    assert command == (
        "python",
        "-m",
        "scripts.run_approval_gated_connector_build_agent",
        "--company-key",
        "hdi",
        "--reviewed-by",
        "jens",
        "--approve-build",
        "--write",
    )


def test_registration_approval_command_uses_existing_final_gate_token() -> None:
    command = registration_approval_command("hdi", "hannover", "jens")

    assert "scripts.run_employer_origin_agent_chain" in command
    assert "--approval-token" in command
    assert REGISTRATION_APPROVAL_TOKEN in command
