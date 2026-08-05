from __future__ import annotations

import pytest

from src.search_intelligence.approval_gated_connector_build import (
    ConnectorBuildRequest,
    ConnectorPaths,
    SourceCandidate,
)
from src.search_intelligence.product_e2e_connector_build_bridge import (
    REQUEST_PERSISTENCE_APPROVAL_TOKEN,
    build_connector_build_bridge_plan,
    classify_connector_build_request,
    select_exact_target_plans,
)


def make_request(
    *,
    candidate_id: int = 57,
    company_key: str = "accompio",
    build_status: str = "build_approval_required",
    queue_action: str | None = "build_candidate_recommended",
    approval_required: bool = True,
    approval_provided: bool = False,
    artifact_generation_allowed: bool = False,
) -> ConnectorBuildRequest:
    return ConnectorBuildRequest(
        candidate=SourceCandidate(
            candidate_id=candidate_id,
            company_key=company_key,
            company_name="Example Employer GmbH",
            candidate_url="https://example.invalid/careers",
            source_name_candidate=f"{company_key}:discovery",
            source_family_candidate=company_key,
            source_target_candidate=None,
            source_type_candidate="employer_origin_career_site",
            status="discovery",
            operational_risk_level="unknown",
        ),
        build_status=build_status,
        recommendation=(
            "request_explicit_build_approval"
            if build_status == "build_approval_required"
            else "stop_before_build"
        ),
        reason="test request",
        build_mode=(
            "connector_candidate_from_build_queue_evidence"
            if build_status == "build_approval_required"
            else "none"
        ),
        approval_required=approval_required,
        approval_provided=approval_provided,
        artifact_generation_allowed=artifact_generation_allowed,
        next_command="python -m scripts.run_approval_gated_connector_build_agent",
        paths=ConnectorPaths(
            module_path=f"src/connectors/{company_key}.py",
            test_path=f"tests/test_{company_key}_connector.py",
            docs_path=(
                "docs/planning/active/source-candidates/"
                f"{company_key}_connector_candidate.md"
            ),
        ),
        boundary={
            "connector_registration_allowed": False,
            "source_activation_allowed": False,
            "bronze_persistence_allowed": False,
        },
        evidence={
            "build_queue_evidence": {
                "present": queue_action is not None,
                "queue_action": queue_action,
                "queue_reason": "test queue reason",
            },
            "generation_plan": {
                "present": False,
                "generation_status": None,
            },
        },
    )


def test_build_approval_classification_is_source_neutral() -> None:
    request = make_request()

    public_plan = build_connector_build_bridge_plan(
        discovery_source_class="public_job_api_discovery",
        request=request,
    )
    origin_plan = build_connector_build_bridge_plan(
        discovery_source_class="existing_origin_evidence",
        request=request,
    )

    assert public_plan.status == origin_plan.status == "operator_decision_required"
    assert (
        public_plan.reason_code
        == origin_plan.reason_code
        == "connector_artifact_build_approval_required"
    )
    assert public_plan.request_persistence_allowed is True
    assert origin_plan.request_persistence_allowed is True
    assert public_plan.artifact_generation_allowed is False


def test_origin_url_repair_is_kept_separate_from_connector_build_approval() -> None:
    request = make_request(
        build_status="manual_review_required",
        queue_action="origin_url_repair_required",
        approval_required=False,
    )

    status, reason = classify_connector_build_request(request)
    plan = build_connector_build_bridge_plan(
        discovery_source_class="existing_origin_evidence",
        request=request,
    )

    assert status == "valid_stop"
    assert reason == "origin_url_repair_required_before_build"
    assert plan.request_persistence_allowed is False


def test_sample_job_review_remains_an_operator_decision() -> None:
    request = make_request(
        build_status="manual_review_required",
        queue_action="sample_job_review_required",
        approval_required=False,
    )

    assert classify_connector_build_request(request) == (
        "operator_decision_required",
        "sample_job_review_required_before_build",
    )


def test_unexpected_artifact_authority_fails_closed() -> None:
    request = make_request(
        build_status="artifact_generation_allowed",
        queue_action="continue_existing_build_flow",
        approval_required=False,
        approval_provided=True,
        artifact_generation_allowed=True,
    )

    plan = build_connector_build_bridge_plan(
        discovery_source_class="public_job_api_discovery",
        request=request,
    )

    assert plan.status == "capability_gap"
    assert plan.reason_code == "unexpected_artifact_generation_authority_in_plan"
    assert plan.request_persistence_allowed is False


def test_exact_persistence_selection_rejects_ineligible_target() -> None:
    eligible = build_connector_build_bridge_plan(
        discovery_source_class="public_job_api_discovery",
        request=make_request(),
    )
    blocked = build_connector_build_bridge_plan(
        discovery_source_class="existing_origin_evidence",
        request=make_request(
            candidate_id=12,
            company_key="adesso",
            build_status="manual_review_required",
            queue_action="origin_url_repair_required",
            approval_required=False,
        ),
    )

    selected = select_exact_target_plans(
        [eligible, blocked],
        requested_targets=["57:accompio"],
        require_request_persistence=True,
    )
    assert selected == (eligible,)

    with pytest.raises(ValueError, match="not eligible for build-request persistence"):
        select_exact_target_plans(
            [eligible, blocked],
            requested_targets=["12:adesso"],
            require_request_persistence=True,
        )


def test_exact_selection_rejects_company_key_drift_and_duplicates() -> None:
    plan = build_connector_build_bridge_plan(
        discovery_source_class="public_job_api_discovery",
        request=make_request(),
    )

    with pytest.raises(ValueError, match="not 'another_company'"):
        select_exact_target_plans(
            [plan],
            requested_targets=["57:another-company"],
            require_request_persistence=False,
        )

    with pytest.raises(ValueError, match="Duplicate candidate target"):
        select_exact_target_plans(
            [plan],
            requested_targets=["57:accompio", "57:accompio"],
            require_request_persistence=False,
        )


def test_request_persistence_has_a_dedicated_token() -> None:
    assert REQUEST_PERSISTENCE_APPROVAL_TOKEN == (
        "approve_product_e2e_connector_build_request_persistence"
    )
