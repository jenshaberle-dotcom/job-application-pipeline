from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

SUCCESS_OUTCOMES = {'tested_found_relevant', 'accepted'}
FAILURE_OUTCOMES = {'tested_no_result', 'rejected'}
NOISE_OUTCOMES = {'tested_found_noise'}
COUNTED_OUTCOMES = SUCCESS_OUTCOMES | FAILURE_OUTCOMES | NOISE_OUTCOMES


@dataclass(frozen=True)
class SearchTermValidationRun:
    suggestion_id: int | None
    candidate_id: int
    company_key: str
    source_name_candidate: str | None
    source_family_candidate: str | None
    suggested_term: str
    validation_scope: str
    outcome: str
    result_count: int
    relevant_count: int
    noise_count: int
    evidence_url: str | None
    notes: str | None
    validated_by: str


@dataclass(frozen=True)
class SearchTermConfidence:
    suggested_term: str
    source_family_candidate: str | None
    validation_scope: str
    sample_size: int
    success_count: int
    failure_count: int
    noise_count: int
    confidence_score: Decimal
    confidence_level: str


def confidence_level(score: Decimal, sample_size: int) -> str:
    if sample_size <= 0:
        return 'unknown'
    if sample_size < 3:
        return 'low'
    if score >= Decimal('70'):
        return 'high'
    if score >= Decimal('40'):
        return 'medium'
    return 'low'


def build_confidence(rows: Iterable[SearchTermValidationRun]) -> list[SearchTermConfidence]:
    buckets: dict[tuple[str, str | None, str], dict[str, int]] = {}
    for row in rows:
        if row.outcome not in COUNTED_OUTCOMES:
            continue
        key = (row.suggested_term.lower().strip(), row.source_family_candidate, row.validation_scope)
        bucket = buckets.setdefault(key, {'sample': 0, 'success': 0, 'failure': 0, 'noise': 0})
        bucket['sample'] += 1
        if row.outcome in SUCCESS_OUTCOMES:
            bucket['success'] += 1
        elif row.outcome in FAILURE_OUTCOMES:
            bucket['failure'] += 1
        elif row.outcome in NOISE_OUTCOMES:
            bucket['noise'] += 1

    confidences: list[SearchTermConfidence] = []
    for (term, source_family, scope), bucket in buckets.items():
        sample = bucket['sample']
        score = Decimal('0') if sample == 0 else (Decimal(bucket['success']) / Decimal(sample) * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        confidences.append(
            SearchTermConfidence(
                suggested_term=term,
                source_family_candidate=source_family,
                validation_scope=scope,
                sample_size=sample,
                success_count=bucket['success'],
                failure_count=bucket['failure'],
                noise_count=bucket['noise'],
                confidence_score=score,
                confidence_level=confidence_level(score, sample),
            )
        )
    return sorted(confidences, key=lambda item: (-item.confidence_score, -item.sample_size, item.suggested_term))
