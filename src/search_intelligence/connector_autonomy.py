from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


A1_POLICY_KEY = "validated_connector_a1"
A1_AUTONOMY_LEVEL = "a1_validated_connector_controlled_activation"
A1_ALLOWED_ACTIVATION_READINESS = "activation_readiness_supported"
LEGACY_APPROVAL_TOKEN = "approve_connector_registration"


@dataclass(frozen=True)
class ConnectorAutonomyPolicy:
    policy_key: str
    autonomy_level: str
    status: str
    policy_version: str
    standing_authorization: bool
    require_connector_validation: bool
    require_exact_activation_readiness: bool
    allowed_activation_readiness: str
    allow_connector_registration: bool
    allow_controlled_source_activation: bool
    allow_bounded_first_ingestion: bool
    allow_recurring_ingestion: bool
    allow_scheduler_mutation: bool
    allow_provider_requests: bool
    allow_ranking_mutation: bool
    allow_application_actions: bool
    approved_by: str | None


@dataclass(frozen=True)
class ConnectorRegistrationAuthorization:
    allowed: bool
    mode: str
    reason: str
    policy_key: str | None = None
    policy_version: str | None = None
    standing_authorized_by: str | None = None


def policy_from_row(row: Mapping[str, Any] | None) -> ConnectorAutonomyPolicy | None:
    if row is None:
        return None
    return ConnectorAutonomyPolicy(
        policy_key=str(row["policy_key"]),
        autonomy_level=str(row["autonomy_level"]),
        status=str(row["status"]),
        policy_version=str(row["policy_version"]),
        standing_authorization=bool(row["standing_authorization"]),
        require_connector_validation=bool(row["require_connector_validation"]),
        require_exact_activation_readiness=bool(row["require_exact_activation_readiness"]),
        allowed_activation_readiness=str(row["allowed_activation_readiness"]),
        allow_connector_registration=bool(row["allow_connector_registration"]),
        allow_controlled_source_activation=bool(row["allow_controlled_source_activation"]),
        allow_bounded_first_ingestion=bool(row["allow_bounded_first_ingestion"]),
        allow_recurring_ingestion=bool(row["allow_recurring_ingestion"]),
        allow_scheduler_mutation=bool(row["allow_scheduler_mutation"]),
        allow_provider_requests=bool(row["allow_provider_requests"]),
        allow_ranking_mutation=bool(row["allow_ranking_mutation"]),
        allow_application_actions=bool(row["allow_application_actions"]),
        approved_by=(str(row["approved_by"]) if row.get("approved_by") else None),
    )


def a1_policy_is_active(policy: ConnectorAutonomyPolicy | None) -> bool:
    if policy is None:
        return False
    return all(
        (
            policy.policy_key == A1_POLICY_KEY,
            policy.autonomy_level == A1_AUTONOMY_LEVEL,
            policy.status == "approved",
            policy.standing_authorization,
            policy.require_connector_validation,
            policy.require_exact_activation_readiness,
            policy.allowed_activation_readiness == A1_ALLOWED_ACTIVATION_READINESS,
            policy.allow_connector_registration,
            policy.allow_controlled_source_activation,
            policy.allow_bounded_first_ingestion,
            not policy.allow_recurring_ingestion,
            not policy.allow_scheduler_mutation,
            not policy.allow_provider_requests,
            not policy.allow_ranking_mutation,
            not policy.allow_application_actions,
            bool(policy.approved_by),
        )
    )


def authorize_connector_registration(
    *,
    validation_ready: bool,
    approval_token: str | None,
    policy: ConnectorAutonomyPolicy | None,
) -> ConnectorRegistrationAuthorization:
    if not validation_ready:
        return ConnectorRegistrationAuthorization(
            allowed=False,
            mode="blocked_missing_connector_validation",
            reason="connector_validation_gate is not passed/ready_for_final_approval",
        )

    if approval_token == LEGACY_APPROVAL_TOKEN:
        return ConnectorRegistrationAuthorization(
            allowed=True,
            mode="legacy_exact_approval_token",
            reason="exact legacy approval token supplied after connector validation",
        )

    if a1_policy_is_active(policy):
        assert policy is not None
        return ConnectorRegistrationAuthorization(
            allowed=True,
            mode="standing_a1_validated_connector_authorization",
            reason="active A1 standing authorization applies after connector validation",
            policy_key=policy.policy_key,
            policy_version=policy.policy_version,
            standing_authorized_by=policy.approved_by,
        )

    return ConnectorRegistrationAuthorization(
        allowed=False,
        mode="approval_token_required",
        reason="exact approval token is required because no active A1 policy applies",
        policy_key=(policy.policy_key if policy else None),
        policy_version=(policy.policy_version if policy else None),
        standing_authorized_by=(policy.approved_by if policy else None),
    )


def activation_readiness_is_a1_eligible(
    *,
    policy: ConnectorAutonomyPolicy | None,
    activation_readiness: str,
) -> bool:
    return bool(
        a1_policy_is_active(policy)
        and policy is not None
        and activation_readiness == policy.allowed_activation_readiness
    )
