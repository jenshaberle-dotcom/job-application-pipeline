"""Approval-safe, narrowly allowlisted Product V1 Control Center actions.

This module reuses the reviewed employer-origin final-approval gate and its audit
repository. It does not expose the legacy approval token. A Control Center action
may therefore pass only through the active validated-connector A1 standing policy.
No connector registration, source activation, ingestion, provider, ranking or
application action is performed here.
"""

from __future__ import annotations

from typing import Any, Mapping

import psycopg

from scripts.run_employer_origin_final_approval_gate_agent import (
    ApprovalRepository,
    ApprovalOutcome,
    SourceCandidate,
    evaluate_final_approval,
)
from src.config import get_database_config

FINAL_APPROVAL_ACTION_PATH = "/api/v1/source-connectors/final-approval"
FINAL_APPROVAL_CONFIRMATION = "approve_final_registration_gate"
ACTION_SCHEMA_VERSION = "product_v1.control_center.final_approval_action.v1"
ACTION_REVIEWED_BY = "product_v1_control_center_a1"
ALLOWED_ACTION_FIELDS = frozenset({"candidate_id", "confirmation"})
STANDING_A1_MODE = "standing_a1_validated_connector_authorization"


class ControlCenterActionStop(RuntimeError):
    """Fail closed before an unreviewed Control Center mutation can occur."""


def parse_final_approval_action_payload(payload: object) -> tuple[int, str]:
    """Validate the exact JSON action shape; reject tokens and arbitrary fields."""

    if not isinstance(payload, Mapping):
        raise ControlCenterActionStop("action payload must be a JSON object")
    keys = {str(key) for key in payload}
    if keys != ALLOWED_ACTION_FIELDS:
        unexpected = sorted(keys - ALLOWED_ACTION_FIELDS)
        missing = sorted(ALLOWED_ACTION_FIELDS - keys)
        detail: list[str] = []
        if unexpected:
            detail.append(f"unexpected fields: {', '.join(unexpected)}")
        if missing:
            detail.append(f"missing fields: {', '.join(missing)}")
        raise ControlCenterActionStop("; ".join(detail) or "invalid action fields")

    raw_candidate_id = payload.get("candidate_id")
    if isinstance(raw_candidate_id, bool) or not isinstance(raw_candidate_id, int):
        raise ControlCenterActionStop("candidate_id must be a positive integer")
    if raw_candidate_id <= 0:
        raise ControlCenterActionStop("candidate_id must be a positive integer")

    confirmation = payload.get("confirmation")
    if confirmation != FINAL_APPROVAL_CONFIRMATION:
        raise ControlCenterActionStop("exact final-approval confirmation is required")
    return raw_candidate_id, FINAL_APPROVAL_CONFIRMATION


def _action_result(
    *,
    candidate: SourceCandidate,
    outcome: ApprovalOutcome,
    recorded: bool,
) -> dict[str, object]:
    authorization = outcome.evidence.get("authorization")
    boundary = outcome.evidence.get("boundary")
    return {
        "schema_version": ACTION_SCHEMA_VERSION,
        "action": "final_approval_gate",
        "status": (
            "applied"
            if outcome.gate_status == "passed"
            else (
                "not_applicable"
                if outcome.gate_status == "not_applicable"
                else "review_required"
            )
        ),
        "candidate": {
            "candidate_id": candidate.id,
            "company_key": candidate.company_key,
            "source_name": candidate.source_name_candidate,
            "candidate_status": candidate.status,
        },
        "gate": {
            "gate_status": outcome.gate_status,
            "decision": outcome.decision,
            "stop_reason": outcome.stop_reason,
            "recorded": recorded,
        },
        "authorization": dict(authorization) if isinstance(authorization, Mapping) else {},
        "boundary": {
            **(dict(boundary) if isinstance(boundary, Mapping) else {}),
            "legacy_approval_token_accepted": False,
            "arbitrary_database_patch_allowed": False,
            "final_approval_gate_review_recorded": recorded,
            "connector_registration_performed": False,
            "source_activation_performed": False,
            "ingestion_performed": False,
            "provider_requests_performed": False,
            "ranking_mutation_performed": False,
            "application_action_performed": False,
        },
    }


def apply_final_approval_action(
    *,
    candidate_id: int,
    confirmation: str,
) -> dict[str, object]:
    """Evaluate and record the existing final-approval gate under A1 only."""

    parsed_candidate_id, _ = parse_final_approval_action_payload(
        {"candidate_id": candidate_id, "confirmation": confirmation}
    )

    with psycopg.connect(**get_database_config()) as conn:
        repo = ApprovalRepository(conn)
        candidate = repo.load_candidate(
            candidate_id=parsed_candidate_id,
            company_key=None,
        )
        gates = repo.load_gates(candidate.id)
        autonomy_policy = repo.load_autonomy_policy()
        outcome = evaluate_final_approval(
            candidate=candidate,
            gates=gates,
            approval_token=None,
            approved_by=ACTION_REVIEWED_BY,
            autonomy_policy=autonomy_policy,
        )

        authorization = outcome.evidence.get("authorization")
        authorization_mode = (
            str(authorization.get("mode"))
            if isinstance(authorization, Mapping)
            else ""
        )
        if outcome.gate_status == "passed" and authorization_mode != STANDING_A1_MODE:
            raise ControlCenterActionStop(
                "final approval may pass through the Control Center only via active A1 standing authorization"
            )

        repo.record_gate(candidate=candidate, outcome=outcome)
        conn.commit()

    return _action_result(candidate=candidate, outcome=outcome, recorded=True)


__all__ = [
    "ACTION_REVIEWED_BY",
    "ACTION_SCHEMA_VERSION",
    "ALLOWED_ACTION_FIELDS",
    "ControlCenterActionStop",
    "FINAL_APPROVAL_ACTION_PATH",
    "FINAL_APPROVAL_CONFIRMATION",
    "apply_final_approval_action",
    "parse_final_approval_action_payload",
]
