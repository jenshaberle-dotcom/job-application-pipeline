"""Plan durable StepStone employer-candidate persistence without side effects.

StepStone review observations are durable evidence, but they are not canonical
employer-origin candidates. This module closes that semantic gap by planning a
low-risk discovery candidate for every valid newly observed employer while
matching existing employer families conservatively.

The module performs no database or network I/O and never activates connectors,
sources, schedulers, Bronze/Silver ingestion, providers, or applications.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from src.normalization.company_keys import (
    find_matching_company_key,
    normalize_company_key,
)
from src.search_intelligence.market_sensor_candidate_promotion_batch import (
    source_family_for_company_key,
    source_name_candidate_for_company_key,
)

PersistenceAction = Literal[
    "created_discovery_candidate",
    "matched_existing_candidate",
    "skipped_invalid_company",
]


@dataclass(frozen=True)
class StepStoneObservedCompany:
    review_id: int
    review_item_id: int | None
    source_name: str
    search_profile_name: str
    search_term: str
    company_key: str
    company_name: str
    evidence_count: int
    sample_titles: tuple[str, ...]
    source_mode: str


@dataclass(frozen=True)
class ExistingEmployerCandidate:
    candidate_id: int
    company_key: str
    company_name: str
    status: str


@dataclass(frozen=True)
class StepStoneCandidatePersistencePlan:
    observation: StepStoneObservedCompany
    normalized_company_key: str
    action: PersistenceAction
    create_allowed: bool
    matched_candidate_id: int | None
    matched_candidate_key: str | None
    source_name_candidate: str | None
    source_family_candidate: str | None
    source_type_candidate: str | None
    risk_level: str | None
    reason: str


def plan_stepstone_candidate_persistence(
    observation: StepStoneObservedCompany,
    existing_candidates: Iterable[ExistingEmployerCandidate],
) -> StepStoneCandidatePersistencePlan:
    """Plan one deduplicated persistence decision for a review observation."""
    company_key = normalize_company_key(
        observation.company_key or observation.company_name
    )
    if not company_key or not observation.company_name.strip():
        return StepStoneCandidatePersistencePlan(
            observation=observation,
            normalized_company_key=company_key,
            action="skipped_invalid_company",
            create_allowed=False,
            matched_candidate_id=None,
            matched_candidate_key=None,
            source_name_candidate=None,
            source_family_candidate=None,
            source_type_candidate=None,
            risk_level=None,
            reason="company observation has no usable canonical key or name",
        )

    candidate_by_key = {
        normalize_company_key(item.company_key or item.company_name): item
        for item in existing_candidates
        if normalize_company_key(item.company_key or item.company_name)
    }
    matched_key = find_matching_company_key(company_key, set(candidate_by_key))
    if matched_key is not None:
        matched = candidate_by_key[matched_key]
        return StepStoneCandidatePersistencePlan(
            observation=observation,
            normalized_company_key=company_key,
            action="matched_existing_candidate",
            create_allowed=False,
            matched_candidate_id=matched.candidate_id,
            matched_candidate_key=matched_key,
            source_name_candidate=None,
            source_family_candidate=None,
            source_type_candidate=None,
            risk_level=None,
            reason=(
                "StepStone employer observation matched an existing "
                f"employer-origin candidate with status={matched.status}"
            ),
        )

    family = source_family_for_company_key(company_key)
    return StepStoneCandidatePersistencePlan(
        observation=observation,
        normalized_company_key=company_key,
        action="created_discovery_candidate",
        create_allowed=True,
        matched_candidate_id=None,
        matched_candidate_key=None,
        source_name_candidate=source_name_candidate_for_company_key(company_key),
        source_family_candidate=family,
        source_type_candidate="employer_origin_career_site",
        risk_level="unknown",
        reason=(
            "new StepStone employer observation is persisted as a discovery "
            "candidate; origin URL and connector remain unresolved"
        ),
    )
