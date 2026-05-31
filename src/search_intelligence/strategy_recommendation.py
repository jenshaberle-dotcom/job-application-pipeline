from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.search_intelligence.autonomy_policy import AutonomyDecision, AutonomyInput, evaluate_autonomy


@dataclass(frozen=True)
class StrategyRecommendationInput:
    candidate_id: int | None
    company_key: str
    source_name_candidate: str | None
    source_family_candidate: str | None
    suggested_term: str
    confidence_score: Decimal
    confidence_level: str
    sample_size: int
    success_count: int
    failure_count: int
    noise_count: int
    false_negative_risk_level: str | None
    false_negative_sighting_count: int


@dataclass(frozen=True)
class SearchStrategyRecommendation:
    candidate_id: int | None
    company_key: str
    source_name_candidate: str | None
    source_family_candidate: str | None
    suggested_term: str
    recommendation_type: str
    recommendation_status: str
    autonomy_level: str
    confidence_score: Decimal
    confidence_level: str
    sample_size: int
    success_count: int
    failure_count: int
    noise_count: int
    false_negative_risk_level: str | None
    false_negative_sighting_count: int
    guardrail_decision: str
    guardrail_summary: dict[str, object]
    reason: str


def build_strategy_recommendations(items: list[StrategyRecommendationInput]) -> list[SearchStrategyRecommendation]:
    recommendations: list[SearchStrategyRecommendation] = []
    for item in items:
        decision: AutonomyDecision = evaluate_autonomy(
            AutonomyInput(
                company_key=item.company_key,
                source_family_candidate=item.source_family_candidate,
                suggested_term=item.suggested_term,
                confidence_score=item.confidence_score,
                confidence_level=item.confidence_level,
                sample_size=item.sample_size,
                success_count=item.success_count,
                failure_count=item.failure_count,
                noise_count=item.noise_count,
                false_negative_risk_level=item.false_negative_risk_level,
                false_negative_sighting_count=item.false_negative_sighting_count,
            )
        )
        recommendations.append(
            SearchStrategyRecommendation(
                candidate_id=item.candidate_id,
                company_key=item.company_key,
                source_name_candidate=item.source_name_candidate,
                source_family_candidate=item.source_family_candidate,
                suggested_term=item.suggested_term,
                recommendation_type=decision.recommendation_type,
                recommendation_status=decision.recommendation_status,
                autonomy_level=decision.autonomy_level,
                confidence_score=item.confidence_score,
                confidence_level=item.confidence_level,
                sample_size=item.sample_size,
                success_count=item.success_count,
                failure_count=item.failure_count,
                noise_count=item.noise_count,
                false_negative_risk_level=item.false_negative_risk_level,
                false_negative_sighting_count=item.false_negative_sighting_count,
                guardrail_decision=decision.guardrail_decision,
                guardrail_summary=decision.guardrail_summary,
                reason=decision.reason,
            )
        )
    return sorted(recommendations, key=lambda rec: (rec.recommendation_status != "auto_eligible", -rec.confidence_score, -rec.sample_size, rec.company_key, rec.suggested_term))
