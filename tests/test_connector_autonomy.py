from __future__ import annotations

from dataclasses import replace

from scripts.run_employer_origin_final_approval_gate_agent import (
    GateReview,
    SourceCandidate,
    evaluate_final_approval,
)
from src.search_intelligence.connector_autonomy import (
    A1_ALLOWED_ACTIVATION_READINESS,
    A1_AUTONOMY_LEVEL,
    A1_POLICY_KEY,
    LEGACY_APPROVAL_TOKEN,
    ConnectorAutonomyPolicy,
    a1_policy_is_active,
    activation_readiness_is_a1_eligible,
    authorize_connector_registration,
)


def policy(*, status: str = "approved") -> ConnectorAutonomyPolicy:
    return ConnectorAutonomyPolicy(
        policy_key=A1_POLICY_KEY,
        autonomy_level=A1_AUTONOMY_LEVEL,
        status=status,
        policy_version="connector-autonomy-a1-test",
        standing_authorization=True,
        require_connector_validation=True,
        require_exact_activation_readiness=True,
        allowed_activation_readiness=A1_ALLOWED_ACTIVATION_READINESS,
        allow_connector_registration=True,
        allow_controlled_source_activation=True,
        allow_bounded_first_ingestion=True,
        allow_recurring_ingestion=False,
        allow_scheduler_mutation=False,
        allow_provider_requests=False,
        allow_ranking_mutation=False,
        allow_application_actions=False,
        approved_by="jens",
    )


def validation_gate() -> GateReview:
    return GateReview(
        gate_name="connector_validation_gate",
        gate_status="passed",
        decision="ready_for_final_approval",
        stop_reason=None,
    )


def candidate() -> SourceCandidate:
    return SourceCandidate(
        id=7,
        company_key="example",
        source_name_candidate="example:discovery",
        status="connector_candidate",
    )


def test_active_a1_policy_is_fail_closed() -> None:
    active = policy()

    assert a1_policy_is_active(active) is True
    assert a1_policy_is_active(replace(active, allow_scheduler_mutation=True)) is False
    assert a1_policy_is_active(replace(active, allow_provider_requests=True)) is False
    assert a1_policy_is_active(replace(active, status="paused")) is False


def test_standing_a1_authorizes_registration_after_validation() -> None:
    authorization = authorize_connector_registration(
        validation_ready=True,
        approval_token=None,
        policy=policy(),
    )

    assert authorization.allowed is True
    assert authorization.mode == "standing_a1_validated_connector_authorization"
    assert authorization.policy_key == A1_POLICY_KEY
    assert authorization.standing_authorized_by == "jens"


def test_missing_validation_blocks_token_and_standing_policy() -> None:
    authorization = authorize_connector_registration(
        validation_ready=False,
        approval_token=LEGACY_APPROVAL_TOKEN,
        policy=policy(),
    )

    assert authorization.allowed is False
    assert authorization.mode == "blocked_missing_connector_validation"


def test_paused_policy_preserves_legacy_token_fallback() -> None:
    without_token = authorize_connector_registration(
        validation_ready=True,
        approval_token=None,
        policy=policy(status="paused"),
    )
    with_token = authorize_connector_registration(
        validation_ready=True,
        approval_token=LEGACY_APPROVAL_TOKEN,
        policy=policy(status="paused"),
    )

    assert without_token.allowed is False
    assert without_token.mode == "approval_token_required"
    assert with_token.allowed is True
    assert with_token.mode == "legacy_exact_approval_token"


def test_activation_requires_exact_supported_readiness() -> None:
    active = policy()

    assert activation_readiness_is_a1_eligible(
        policy=active,
        activation_readiness="activation_readiness_supported",
    )
    assert not activation_readiness_is_a1_eligible(
        policy=active,
        activation_readiness="activation_readiness_supported_with_manual_overlap_review",
    )
    assert not activation_readiness_is_a1_eligible(
        policy=policy(status="paused"),
        activation_readiness="activation_readiness_supported",
    )


def test_final_approval_uses_standing_a1_without_per_candidate_token() -> None:
    outcome = evaluate_final_approval(
        candidate=candidate(),
        gates={"connector_validation_gate": validation_gate()},
        approval_token=None,
        approved_by="connector_autonomy_a1",
        autonomy_policy=policy(),
    )

    assert outcome.gate_status == "passed"
    assert outcome.decision == "approve_connector_registration"
    assert (
        outcome.evidence["authorization"]["mode"]
        == "standing_a1_validated_connector_authorization"
    )
    assert outcome.evidence["boundary"]["source_activation_allowed_by_this_gate"] is False
    assert outcome.evidence["boundary"]["scheduler_mutation_allowed"] is False
