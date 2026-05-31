from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.search_intelligence.false_negative_risk import FalseNegativeRiskAssessment

ACTIONABLE_RISK_LEVELS = {"critical", "high", "medium"}


@dataclass(frozen=True)
class SearchTermSuggestion:
    candidate_id: int
    company_key: str
    company_name: str
    suggested_term: str
    risk_level: str
    evidence_count: int
    last_observed_at: str | None
    reason: str


@dataclass(frozen=True)
class ReassessmentQueueItem:
    candidate_id: int
    company_key: str
    company_name: str
    risk_level: str
    priority: int
    trigger_reason: str
    suggested_search_terms: tuple[str, ...]
    last_observed_at: str | None


def reassessment_priority(risk_level: str, recent_sighting_count: int) -> int:
    base = {
        "critical": 100,
        "high": 75,
        "medium": 50,
    }.get(risk_level, 0)
    return base + min(max(recent_sighting_count, 0), 20)


def actionable_assessments(
    assessments: Iterable[FalseNegativeRiskAssessment],
) -> list[FalseNegativeRiskAssessment]:
    return [
        assessment
        for assessment in assessments
        if assessment.risk_level in ACTIONABLE_RISK_LEVELS
        and assessment.sighting_count > 0
    ]


def build_search_term_suggestions(
    assessments: Iterable[FalseNegativeRiskAssessment],
) -> list[SearchTermSuggestion]:
    suggestions: list[SearchTermSuggestion] = []
    for assessment in actionable_assessments(assessments):
        for term in assessment.suggested_search_terms:
            suggestions.append(
                SearchTermSuggestion(
                    candidate_id=assessment.candidate_id,
                    company_key=assessment.company_key,
                    company_name=assessment.company_name,
                    suggested_term=term,
                    risk_level=assessment.risk_level,
                    evidence_count=assessment.sighting_count,
                    last_observed_at=assessment.last_observed_at,
                    reason=assessment.reason,
                )
            )
    return suggestions


def build_reassessment_queue_items(
    assessments: Iterable[FalseNegativeRiskAssessment],
) -> list[ReassessmentQueueItem]:
    items: list[ReassessmentQueueItem] = []
    for assessment in actionable_assessments(assessments):
        items.append(
            ReassessmentQueueItem(
                candidate_id=assessment.candidate_id,
                company_key=assessment.company_key,
                company_name=assessment.company_name,
                risk_level=assessment.risk_level,
                priority=reassessment_priority(
                    assessment.risk_level,
                    assessment.recent_sighting_count,
                ),
                trigger_reason=assessment.reason,
                suggested_search_terms=assessment.suggested_search_terms,
                last_observed_at=assessment.last_observed_at,
            )
        )
    return sorted(items, key=lambda item: (-item.priority, item.company_name.lower()))
