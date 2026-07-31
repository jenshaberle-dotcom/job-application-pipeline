"""Quality scoring and route recommendation for the origin LLM campaign."""

from __future__ import annotations

from typing import Mapping, Sequence

from src.search_intelligence.origin_llm_adjudication import (
    LLMAdjudication,
    LLMAdjudicationResult,
)
from src.search_intelligence.origin_llm_model_campaign_types import (
    BenchmarkExpectation,
    CaseScore,
    EscalationSimulation,
    ModelCallObservation,
)
from src.search_intelligence.origin_source_evidence import OriginEvidenceDecision


def parse_expectations(payload: Mapping[str, object]) -> tuple[BenchmarkExpectation, ...]:
    if payload.get("schema_version") != "origin_llm_model_benchmark_contract.v1":
        raise ValueError("unsupported benchmark expectation schema")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("benchmark contract cases must be an array")
    cases: list[BenchmarkExpectation] = []
    for raw in raw_cases:
        if not isinstance(raw, Mapping):
            raise ValueError("benchmark case must be an object")
        cases.append(
            BenchmarkExpectation(
                case_id=str(raw["case_id"]),
                company_name_contains=str(raw["company_name_contains"]).casefold(),
                expected_manual_review=bool(raw["expected_manual_review"]),
                acceptable_url_contains=tuple(
                    str(item).casefold() for item in raw.get("acceptable_url_contains", [])
                ),
                acceptable_source_grades=tuple(
                    str(item) for item in raw.get("acceptable_source_grades", [])
                ),
                expected_locale=(
                    None
                    if raw.get("expected_locale") is None
                    else str(raw["expected_locale"]).casefold()
                ),
                weight=float(raw.get("weight") or 1.0),
                notes=str(raw.get("notes") or ""),
            )
        )
    return tuple(cases)


def match_expectation(
    decision: OriginEvidenceDecision,
    expectations: Sequence[BenchmarkExpectation],
) -> BenchmarkExpectation | None:
    name = decision.company_name.casefold()
    matches = [item for item in expectations if item.company_name_contains in name]
    if len(matches) > 1:
        raise ValueError(f"multiple benchmark expectations match {decision.company_name}")
    return matches[0] if matches else None


def _effective_candidate_id(
    decision: OriginEvidenceDecision,
    adjudication: LLMAdjudication,
) -> str | None:
    if adjudication.decision == "confirm_deterministic":
        return decision.selected_candidate_id
    return adjudication.recommended_candidate_id


def _assessment_by_id(decision: OriginEvidenceDecision, candidate_id: str | None):
    if candidate_id is None:
        return None
    return next(
        (item for item in decision.assessments if item.candidate_id == candidate_id),
        None,
    )


def score_observation(
    decision: OriginEvidenceDecision,
    observation: ModelCallObservation,
    expectation: BenchmarkExpectation,
) -> CaseScore:
    reasons: list[str] = []
    result = observation.result
    if result.status != "completed" or result.adjudication is None:
        return CaseScore(
            case_id=expectation.case_id,
            company_key=decision.company_key,
            model=observation.model_requested,
            weight=expectation.weight,
            score=0.0,
            critical_failure=True,
            effective_candidate_id=None,
            effective_candidate_url=None,
            reasons=("provider_result_not_completed",),
        )

    adjudication = result.adjudication
    score = 0.20
    critical_failure = False
    effective_id = _effective_candidate_id(decision, adjudication)
    assessment = _assessment_by_id(decision, effective_id)
    effective_url = assessment.final_url if assessment is not None else None

    actual_manual = bool(
        adjudication.manual_review_required
        or adjudication.decision in {"manual_review_required", "abstain"}
    )
    if actual_manual == expectation.expected_manual_review:
        score += 0.35
        reasons.append("manual_review_expectation_matched")
    else:
        reasons.append("manual_review_expectation_missed")

    if expectation.expected_manual_review:
        if adjudication.decision in {"manual_review_required", "abstain"}:
            score += 0.35
            reasons.append("safe_ambiguity_handling")
        else:
            critical_failure = True
            reasons.append("unsafe_resolution_of_expected_ambiguity")
        if effective_id is None or adjudication.manual_review_required:
            score += 0.10
        return CaseScore(
            case_id=expectation.case_id,
            company_key=decision.company_key,
            model=observation.model_requested,
            weight=expectation.weight,
            score=round(min(score, 1.0), 4),
            critical_failure=critical_failure,
            effective_candidate_id=effective_id,
            effective_candidate_url=effective_url,
            reasons=tuple(reasons),
        )

    if assessment is None:
        reasons.append("no_effective_candidate")
        critical_failure = True
    else:
        url_lower = assessment.final_url.casefold()
        if not expectation.acceptable_url_contains or any(
            token in url_lower for token in expectation.acceptable_url_contains
        ):
            score += 0.25
            reasons.append("candidate_url_expectation_matched")
        else:
            reasons.append("candidate_url_expectation_missed")
        if not expectation.acceptable_source_grades or (
            assessment.source_grade in expectation.acceptable_source_grades
        ):
            score += 0.10
            reasons.append("source_grade_expectation_matched")
        else:
            reasons.append("source_grade_expectation_missed")
        if expectation.expected_locale is None or (
            assessment.locale.casefold().startswith(expectation.expected_locale)
        ):
            score += 0.10
            reasons.append("locale_expectation_matched")
        else:
            reasons.append("locale_expectation_missed")

    return CaseScore(
        case_id=expectation.case_id,
        company_key=decision.company_key,
        model=observation.model_requested,
        weight=expectation.weight,
        score=round(min(score, 1.0), 4),
        critical_failure=critical_failure,
        effective_candidate_id=effective_id,
        effective_candidate_url=effective_url,
        reasons=tuple(reasons),
    )


def should_escalate(
    decision: OriginEvidenceDecision,
    primary: LLMAdjudicationResult,
) -> str | None:
    if primary.status != "completed" or primary.adjudication is None:
        return "primary_failed_closed"
    adjudication = primary.adjudication
    if adjudication.decision == "abstain":
        return "primary_abstained"
    if (
        adjudication.decision == "prefer_alternative"
        and decision.selected_candidate_id is not None
        and adjudication.recommended_candidate_id != decision.selected_candidate_id
        and decision.selection_margin >= 0.15
    ):
        return "provider_conflicts_with_strong_deterministic_winner"
    if decision.manual_review_required and not adjudication.manual_review_required:
        return "provider_attempts_to_clear_deterministic_manual_review"
    if adjudication.manual_review_required and len(decision.assessments) >= 2:
        top_two = decision.assessments[:2]
        if all(
            item.evidence_completeness >= 0.45
            and item.job_inventory_state != "fetch_failed"
            for item in top_two
        ):
            return "high_evidence_semantic_ambiguity"
    return None


def observations_agree(
    first: LLMAdjudicationResult,
    second: LLMAdjudicationResult,
) -> bool:
    if first.adjudication is None or second.adjudication is None:
        return False
    return (
        first.adjudication.decision == second.adjudication.decision
        and first.adjudication.recommended_candidate_id
        == second.adjudication.recommended_candidate_id
        and first.adjudication.manual_review_required
        == second.adjudication.manual_review_required
        and first.adjudication.entity_relationship
        == second.adjudication.entity_relationship
        and first.adjudication.origin_assessment
        == second.adjudication.origin_assessment
    )


def simulate_escalation(
    *,
    decision: OriginEvidenceDecision,
    primary_observation: ModelCallObservation,
    escalation_observation: ModelCallObservation,
    primary_score: CaseScore,
    escalation_score: CaseScore,
) -> EscalationSimulation:
    trigger = should_escalate(decision, primary_observation.result)
    if trigger is None:
        outcome = "not_triggered"
    elif observations_agree(primary_observation.result, escalation_observation.result):
        outcome = "provider_consensus"
    elif escalation_score.score > primary_score.score:
        outcome = "escalation_improved_quality"
    else:
        outcome = "provider_disagreement_manual_review"
    lift = round(escalation_score.score - primary_score.score, 4)
    corrected = bool(
        trigger is not None
        and primary_score.score < 0.80
        and escalation_score.score >= 0.85
        and not escalation_score.critical_failure
    )
    return EscalationSimulation(
        company_key=decision.company_key,
        trigger_reason=trigger,
        primary_model=primary_observation.model_requested,
        escalation_model=escalation_observation.model_requested,
        primary_score=primary_score.score,
        escalation_score=escalation_score.score,
        score_lift=lift,
        corrected=corrected,
        outcome=outcome,
    )
