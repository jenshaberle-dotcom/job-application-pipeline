"""Real bounded two-stage escalation execution."""

from __future__ import annotations

from src.search_intelligence.origin_source_evidence import OriginEvidenceDecision
from src.search_intelligence.origin_llm_model_campaign_types import EscalatedAdjudicationRun
from src.search_intelligence.origin_llm_model_campaign_provider import (
    Transport,
    _requests_transport,
    adjudicate_model,
)
from src.search_intelligence.origin_llm_model_campaign_evaluation import (
    observations_agree,
    should_escalate,
)


def adjudicate_with_escalation(
    decision: OriginEvidenceDecision,
    *,
    api_key: str,
    primary_model: str,
    escalation_model: str,
    reasoning_effort: str = "low",
    max_output_tokens: int = 900,
    timeout_seconds: float = 60.0,
    transport: Transport = _requests_transport,
) -> EscalatedAdjudicationRun:
    """Run at most two provider calls and never convert them into mutation truth."""

    primary = adjudicate_model(
        decision,
        api_key=api_key,
        model=primary_model,
        reasoning_effort=reasoning_effort,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        transport=transport,
    )
    trigger = should_escalate(decision, primary.result)
    if trigger is None or not str(escalation_model or "").strip():
        return EscalatedAdjudicationRun(
            company_key=decision.company_key,
            company_name=decision.company_name,
            primary=primary,
            escalation=None,
            trigger_reason=trigger,
            outcome="primary_review_signal_only",
        )
    escalation = adjudicate_model(
        decision,
        api_key=api_key,
        model=escalation_model,
        reasoning_effort=reasoning_effort,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        transport=transport,
    )
    if observations_agree(primary.result, escalation.result):
        outcome = "provider_consensus_for_operator_review"
    elif primary.result.adjudication is None and escalation.result.adjudication is not None:
        outcome = "escalation_repaired_primary_failure_for_operator_review"
    else:
        outcome = "provider_disagreement_manual_review_required"
    return EscalatedAdjudicationRun(
        company_key=decision.company_key,
        company_name=decision.company_name,
        primary=primary,
        escalation=escalation,
        trigger_reason=trigger,
        outcome=outcome,
    )
