"""Pure decision contract for A1 controlled source activation."""
from __future__ import annotations

from dataclasses import dataclass

from src.search_intelligence.connector_autonomy import (
    ConnectorAutonomyPolicy,
    activation_readiness_is_a1_eligible,
)


@dataclass(frozen=True)
class ControlledActivationDecision:
    allowed: bool
    status: str
    reason: str


def controlled_profile_name(company_key: str) -> str:
    normalized = company_key.strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        raise ValueError("company_key must not be empty")
    return f"{normalized}_controlled_hannover_precision"


def decide_controlled_activation(
    *,
    connector_validation_passed: bool,
    final_approval_passed: bool,
    candidate_status: str,
    active_profile_count: int,
    activation_readiness: str,
    policy: ConnectorAutonomyPolicy | None,
) -> ControlledActivationDecision:
    if candidate_status == "active_controlled" or active_profile_count > 0:
        return ControlledActivationDecision(
            allowed=False,
            status="controlled_activation_blocked_already_active",
            reason="Candidate or source already has controlled activation truth.",
        )

    if not connector_validation_passed:
        return ControlledActivationDecision(
            allowed=False,
            status="controlled_activation_blocked_missing_validation",
            reason=(
                "connector_validation_gate must be passed with "
                "ready_for_final_approval before A1 activation."
            ),
        )

    if not final_approval_passed:
        return ControlledActivationDecision(
            allowed=False,
            status="controlled_activation_blocked_missing_final_approval",
            reason=(
                "final_approval_gate must be passed with "
                "approve_connector_registration before A1 activation."
            ),
        )

    if not activation_readiness_is_a1_eligible(
        policy=policy,
        activation_readiness=activation_readiness,
    ):
        return ControlledActivationDecision(
            allowed=False,
            status="controlled_activation_blocked_a1_or_readiness",
            reason=(
                "Active A1 standing authorization and exact "
                "activation_readiness_supported are both required."
            ),
        )

    return ControlledActivationDecision(
        allowed=True,
        status="controlled_activation_apply_ready",
        reason=(
            "Validated connector, final approval, active A1 policy and exact fresh "
            "activation readiness support controlled activation."
        ),
    )
