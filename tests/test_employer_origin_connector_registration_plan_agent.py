from __future__ import annotations

from scripts.run_employer_origin_connector_build_readiness_agent import (
    REQUIRED_PASSED_GATES,
    GateReview,
    SourceCandidate,
)
from scripts.run_employer_origin_connector_registration_plan_agent import (
    build_registration_plan,
    render_markdown,
)


def candidate() -> SourceCandidate:
    return SourceCandidate(
        id=2,
        company_key="example",
        company_name="Example AG",
        candidate_url="https://example.test/jobs",
        source_name_candidate="example:hannover",
        source_family_candidate="example",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="connector_candidate",
        risk_level="low",
    )


def gate(name: str, status: str = "passed", decision: str = "continue", evidence: dict | None = None) -> GateReview:
    return GateReview(
        gate_name=name,
        gate_status=status,
        decision=decision,
        stop_reason=None,
        evidence=evidence or {},
    )


def gates() -> dict[str, GateReview]:
    result = {name: gate(name) for name in REQUIRED_PASSED_GATES}
    result["connector_candidate_gate"] = gate(
        "connector_candidate_gate",
        decision="build_connector_candidate",
        evidence={
            "connector_candidate_spec": {
                "recommended_connector": {
                    "module_path": "src/connectors/example.py",
                    "test_path": "tests/test_example_connector.py",
                    "class_name": "ExampleConnector",
                    "source_name": "example:hannover",
                    "source_type": "employer_origin_career_site",
                },
                "detail_evidence": {
                    "detail_urls": ["https://example.test/jobs/product-owner-data-platform"]
                },
            }
        },
    )
    return result


def test_registration_plan_requires_manual_approval_and_forbids_activation() -> None:
    plan = build_registration_plan(candidate(), gates())

    assert plan.readiness_status == "ready"
    assert plan.required_manual_approval_token == "approve_connector_registration"
    assert plan.module_path == "src/connectors/example.py"
    assert any("Do not write Bronze" in action for action in plan.forbidden_actions)
    assert any("Do not activate recurring ingestion" in action for action in plan.forbidden_actions)


def test_registration_plan_markdown_contains_boundary_and_validation() -> None:
    markdown = render_markdown(build_registration_plan(candidate(), gates()))

    assert "# Connector Registration Plan" in markdown
    assert "approve_connector_registration" in markdown
    assert "pytest -q" in markdown
    assert "does not register, activate, ingest or schedule anything" in markdown
