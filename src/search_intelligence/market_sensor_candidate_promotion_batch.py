"""EO-002 market-sensor company promotion into employer-origin candidates.

This module contains deterministic planning logic only. It turns explicit
market-sensor company selections into reviewable discovery-candidate creation
plans. It does not browse, run gates, activate sources, build connectors, or
write Bronze/Silver data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

DIRECT_CREATE_DECISIONS = {"create_candidate_recommended"}
MANUAL_REVIEW_DECISIONS = {"manual_review_required"}
DEFER_DECISIONS = {"insufficient_evidence"}
NOISE_DECISIONS = {"suppress_as_noise"}


@dataclass(frozen=True)
class MarketSensorPromotionInput:
    """One candidate-expansion review item selected for EO-002."""

    item_id: int
    review_id: int
    company_key: str
    company_name: str
    source_name: str
    decision: str
    priority: int
    evidence_count: int
    known_candidate_id: int | None = None
    known_candidate_status: str | None = None
    recommended_next_action: str = ""
    reason: str = ""


@dataclass(frozen=True)
class CandidateCreationPlan:
    """One explicit market-sensor to origin-candidate promotion plan."""

    item_id: int | None
    review_id: int | None
    company_key: str
    company_name: str
    source_decision: str | None
    action: str
    create_allowed: bool
    reason: str
    source_name_candidate: str | None = None
    source_family_candidate: str | None = None
    source_target_candidate: str | None = None
    source_type_candidate: str | None = None
    candidate_url: str | None = None
    risk_level: str | None = None
    created_candidate_id: int | None = None


@dataclass(frozen=True)
class PromotionBatchPlan:
    """Reviewable EO-002 batch plan."""

    requested_company_keys: tuple[str, ...]
    items: tuple[CandidateCreationPlan, ...]
    include_manual_review_required: bool

    @property
    def create_count(self) -> int:
        return sum(1 for item in self.items if item.create_allowed)

    @property
    def blocked_count(self) -> int:
        return sum(1 for item in self.items if not item.create_allowed)

    @property
    def created_count(self) -> int:
        return sum(1 for item in self.items if item.created_candidate_id is not None)


def normalize_company_key(company_key: str) -> str:
    return company_key.strip().lower()


def source_family_for_company_key(company_key: str) -> str:
    return normalize_company_key(company_key).replace(" ", "_")


def source_name_candidate_for_company_key(company_key: str) -> str:
    return f"{source_family_for_company_key(company_key)}:discovery"


def _missing_plan(company_key: str) -> CandidateCreationPlan:
    return CandidateCreationPlan(
        item_id=None,
        review_id=None,
        company_key=company_key,
        company_name="",
        source_decision=None,
        action="missing_market_sensor_item",
        create_allowed=False,
        reason="requested company_key was not found in the selected market-sensor review",
    )


def build_creation_plan_for_item(
    item: MarketSensorPromotionInput,
    *,
    include_manual_review_required: bool,
    existing_company_keys: set[str],
) -> CandidateCreationPlan:
    """Build one candidate-creation plan without mutating the database."""

    normalized_key = normalize_company_key(item.company_key)
    family = source_family_for_company_key(item.company_key)
    source_name_candidate = source_name_candidate_for_company_key(item.company_key)

    if normalized_key in existing_company_keys or item.known_candidate_id is not None:
        return CandidateCreationPlan(
            item_id=item.item_id,
            review_id=item.review_id,
            company_key=item.company_key,
            company_name=item.company_name,
            source_decision=item.decision,
            action="skip_existing_candidate",
            create_allowed=False,
            reason="employer-origin candidate already exists; refusing duplicate creation",
            source_name_candidate=source_name_candidate,
            source_family_candidate=family,
            source_type_candidate="employer_origin_career_site",
            risk_level="low",
        )

    if item.decision in DIRECT_CREATE_DECISIONS:
        return CandidateCreationPlan(
            item_id=item.item_id,
            review_id=item.review_id,
            company_key=item.company_key,
            company_name=item.company_name,
            source_decision=item.decision,
            action="create_discovery_candidate",
            create_allowed=True,
            reason="market-sensor evidence recommends candidate creation",
            source_name_candidate=source_name_candidate,
            source_family_candidate=family,
            source_target_candidate=None,
            source_type_candidate="employer_origin_career_site",
            candidate_url=None,
            risk_level="unknown",
        )

    if item.decision in MANUAL_REVIEW_DECISIONS:
        if include_manual_review_required:
            return CandidateCreationPlan(
                item_id=item.item_id,
                review_id=item.review_id,
                company_key=item.company_key,
                company_name=item.company_name,
                source_decision=item.decision,
                action="create_discovery_candidate_with_manual_review_opt_in",
                create_allowed=True,
                reason="manual-review market-sensor candidate explicitly included by reviewer",
                source_name_candidate=source_name_candidate,
                source_family_candidate=family,
                source_target_candidate=None,
                source_type_candidate="employer_origin_career_site",
                candidate_url=None,
                risk_level="medium",
            )
        return CandidateCreationPlan(
            item_id=item.item_id,
            review_id=item.review_id,
            company_key=item.company_key,
            company_name=item.company_name,
            source_decision=item.decision,
            action="requires_manual_review_opt_in",
            create_allowed=False,
            reason="manual-review candidate requires --include-manual-review-required",
            source_name_candidate=source_name_candidate,
            source_family_candidate=family,
            source_type_candidate="employer_origin_career_site",
            risk_level="medium",
        )

    if item.decision in DEFER_DECISIONS:
        action = "defer_insufficient_evidence"
        reason = "market-sensor evidence is insufficient for candidate creation"
    elif item.decision in NOISE_DECISIONS:
        action = "skip_noise"
        reason = "market-sensor item is classified as noise"
    else:
        action = "unsupported_market_sensor_decision"
        reason = f"unsupported market-sensor decision: {item.decision}"

    return CandidateCreationPlan(
        item_id=item.item_id,
        review_id=item.review_id,
        company_key=item.company_key,
        company_name=item.company_name,
        source_decision=item.decision,
        action=action,
        create_allowed=False,
        reason=reason,
        source_name_candidate=source_name_candidate,
        source_family_candidate=family,
        source_type_candidate="employer_origin_career_site",
        risk_level="blocked" if item.decision in NOISE_DECISIONS else "unknown",
    )


def build_promotion_batch_plan(
    items: Iterable[MarketSensorPromotionInput],
    *,
    requested_company_keys: Sequence[str],
    include_manual_review_required: bool,
    existing_company_keys: set[str],
) -> PromotionBatchPlan:
    """Build EO-002 batch plan in explicit requested-company order."""

    requested_keys = tuple(normalize_company_key(company_key) for company_key in requested_company_keys)
    item_by_key = {normalize_company_key(item.company_key): item for item in items}
    existing_keys = {normalize_company_key(company_key) for company_key in existing_company_keys}

    plans: list[CandidateCreationPlan] = []
    for company_key in requested_keys:
        item = item_by_key.get(company_key)
        if item is None:
            plans.append(_missing_plan(company_key))
            continue
        plans.append(
            build_creation_plan_for_item(
                item,
                include_manual_review_required=include_manual_review_required,
                existing_company_keys=existing_keys,
            )
        )

    return PromotionBatchPlan(
        requested_company_keys=requested_keys,
        items=tuple(plans),
        include_manual_review_required=include_manual_review_required,
    )
