from __future__ import annotations

from scripts.run_employer_origin_registration_execution_plan_agent import (
    GateReview,
    SourceCandidate,
    build_execution_plan,
    render_markdown,
)


def candidate() -> SourceCandidate:
    return SourceCandidate(
        id=1,
        company_key="example",
        company_name="Example AG",
        source_name_candidate="example:hannover",
        source_family_candidate="example",
        source_type_candidate="employer_origin_career_site",
        status="connector_candidate",
    )


def test_execution_plan_is_blocked_without_final_approval() -> None:
    plan = build_execution_plan(candidate(), {})

    assert plan.allowed is False
    assert plan.reason == "final approval gate is not passed/approve_connector_registration"


def test_execution_plan_allowed_after_final_approval_and_remains_non_activating() -> None:
    plan = build_execution_plan(
        candidate(),
        {
            "final_approval_gate": GateReview(
                gate_name="final_approval_gate",
                gate_status="passed",
                decision="approve_connector_registration",
                stop_reason=None,
            )
        },
    )

    assert plan.allowed is True
    assert any("Do not write Bronze" in item for item in plan.forbidden)
    assert plan.evidence["boundary"]["source_activation_allowed"] is False
    assert plan.evidence["agent"] == "s4c_registration_execution_plan_agent"
    assert plan.evidence["boundary"]["registration_target"] == "src.connectors.registry / src.connectors.employer_origin_registry"


def test_execution_plan_markdown_contains_boundary() -> None:
    markdown = render_markdown(build_execution_plan(candidate(), {}))

    assert "Registration Execution Plan" in markdown
    assert "Forbidden Actions" in markdown
    assert "does not modify connector registration" in markdown
    assert "code-backed connector registry" in markdown

def test_execution_plan_is_not_allowed_for_active_controlled_source() -> None:
    active = SourceCandidate(
        id=1,
        company_key="finanz_informatik",
        company_name="Finanz Informatik GmbH & Co. KG",
        source_name_candidate="finanz_informatik:hannover",
        source_family_candidate="finanz_informatik",
        source_type_candidate="employer_origin_career_site",
        status="active_controlled",
    )

    plan = build_execution_plan(
        active,
        {
            "final_approval_gate": GateReview(
                gate_name="final_approval_gate",
                gate_status="passed",
                decision="approve_connector_registration",
                stop_reason=None,
            )
        },
    )

    assert plan.allowed is False
    assert plan.reason == "candidate is already active_controlled"
