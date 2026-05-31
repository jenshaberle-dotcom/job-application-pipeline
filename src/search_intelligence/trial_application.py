from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any


TRIAL_APPROVAL_TOKEN = "approve_trial_search_term"


@dataclass(frozen=True)
class StrategyRecommendationForTrial:
    recommendation_id: int
    candidate_id: int | None
    company_key: str
    source_name_candidate: str | None
    source_family_candidate: str | None
    suggested_term: str
    recommendation_type: str
    recommendation_status: str
    autonomy_level: str
    guardrail_decision: str
    confidence_score: Decimal
    sample_size: int
    false_negative_risk_level: str | None
    guardrail_summary: dict[str, Any]
    reason: str


@dataclass(frozen=True)
class TrialApplicationPlan:
    recommendation_id: int
    candidate_id: int | None
    company_key: str
    source_name_candidate: str | None
    source_family_candidate: str | None
    suggested_term: str
    trial_scope: str
    trial_status: str
    autonomy_level: str
    guardrail_decision: str
    trial_duration_days: int
    trial_expires_at: datetime
    max_result_volume: int
    max_noise_rate: Decimal
    apply_allowed: bool
    approval_required: bool
    reason: str


def _decimal_from_guardrail(summary: dict[str, Any], key: str, default: str) -> Decimal:
    return Decimal(str(summary.get(key, default)))


def _int_from_guardrail(summary: dict[str, Any], key: str, default: int) -> int:
    return int(summary.get(key, default))


def build_trial_application_plans(
    recommendations: list[StrategyRecommendationForTrial],
    *,
    approval_token: str | None = None,
    allow_auto_eligible: bool = False,
    now: datetime | None = None,
) -> list[TrialApplicationPlan]:
    current_time = now or datetime.now(timezone.utc)
    plans: list[TrialApplicationPlan] = []

    for item in recommendations:
        if item.recommendation_type != "ADD_TRIAL_TERM":
            continue

        if item.recommendation_status not in {"pending_review", "auto_eligible"}:
            continue

        duration_days = _int_from_guardrail(item.guardrail_summary, "trial_duration_days", 14)
        max_result_volume = _int_from_guardrail(item.guardrail_summary, "max_result_volume", 25)
        max_noise_rate = _decimal_from_guardrail(item.guardrail_summary, "max_noise_rate", "0.30")

        is_auto_eligible = item.recommendation_status == "auto_eligible"
        has_manual_approval = approval_token == TRIAL_APPROVAL_TOKEN
        apply_allowed = has_manual_approval or (is_auto_eligible and allow_auto_eligible)
        approval_required = not apply_allowed

        if is_auto_eligible and allow_auto_eligible:
            reason = "Auto-eligible recommendation may be applied as a bounded trial under guardrails."
        elif has_manual_approval:
            reason = "Explicit approval token allows this bounded trial term to be applied."
        else:
            reason = "Bounded trial recommendation exists but requires explicit approval or auto-eligible mode."

        plans.append(
            TrialApplicationPlan(
                recommendation_id=item.recommendation_id,
                candidate_id=item.candidate_id,
                company_key=item.company_key,
                source_name_candidate=item.source_name_candidate,
                source_family_candidate=item.source_family_candidate,
                suggested_term=item.suggested_term,
                trial_scope="source_candidate",
                trial_status="active",
                autonomy_level=item.autonomy_level,
                guardrail_decision=item.guardrail_decision,
                trial_duration_days=duration_days,
                trial_expires_at=current_time + timedelta(days=duration_days),
                max_result_volume=max_result_volume,
                max_noise_rate=max_noise_rate,
                apply_allowed=apply_allowed,
                approval_required=approval_required,
                reason=reason,
            )
        )

    return plans
