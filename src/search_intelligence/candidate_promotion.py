"""Candidate Promotion Gate for market-observed companies.

S7J intentionally separates three concerns:

1. Candidate Expansion observes and classifies market evidence.
2. Candidate Promotion decides whether this evidence may become a modeled
   employer-origin candidate.
3. Origin Source Discovery later selects a safe origin URL.

Because the real origin URL may not be known at promotion time, S7J can create
``employer_origin_source_candidates`` rows in ``discovery`` state with a NULL
``candidate_url``. This is intentional and avoids poisoning origin evidence with
aggregator URLs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


BOUNDARY: dict[str, bool] = {
    "web_browsing_allowed": False,
    "candidate_creation_requires_explicit_flag": True,
    "connector_build_allowed": False,
    "connector_registration_allowed": False,
    "source_activation_allowed": False,
    "bronze_persistence_allowed": False,
    "scheduler_change_allowed": False,
    "csv_or_export_inputs_used": False,
}

DIRECT_PROMOTION_DECISIONS = {"create_candidate_recommended"}
MANUAL_PROMOTION_DECISIONS = {"manual_review_required"}
DEFERRED_PROMOTION_DECISIONS = {"insufficient_evidence"}
REJECTED_PROMOTION_DECISIONS = {"suppress_as_noise"}
SKIPPED_PROMOTION_DECISIONS = {"already_known", "active_candidate_monitoring"}


@dataclass(frozen=True)
class CandidateExpansionItem:
    """One persisted item from a candidate-expansion review."""

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
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidatePromotionItem:
    """Decision for promoting one market-observed company."""

    candidate_expansion_item_id: int
    candidate_expansion_review_id: int
    company_key: str
    company_name: str
    source_name: str
    source_decision: str
    promotion_decision: str
    priority: int
    evidence_count: int
    source_name_candidate: str
    source_family_candidate: str
    source_target_candidate: str | None
    source_type_candidate: str
    candidate_url: str | None
    risk_level: str
    reason: str
    recommended_next_action: str
    created_candidate_id: int | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidatePromotionReview:
    """Promotion review over one candidate-expansion review."""

    candidate_expansion_review_id: int
    items: tuple[CandidatePromotionItem, ...]
    boundary: dict[str, bool] = field(default_factory=lambda: dict(BOUNDARY))

    @property
    def item_count(self) -> int:
        return len(self.items)

    def count(self, decision: str) -> int:
        return sum(1 for item in self.items if item.promotion_decision == decision)

    @property
    def promotion_recommended_count(self) -> int:
        return self.count("promotion_recommended")

    @property
    def manual_review_count(self) -> int:
        return self.count("promotion_manual_review_required")

    @property
    def deferred_count(self) -> int:
        return self.count("promotion_deferred")

    @property
    def rejected_count(self) -> int:
        return self.count("promotion_rejected_noise")

    @property
    def skipped_existing_count(self) -> int:
        return self.count("promotion_skipped_existing")

    @property
    def created_candidate_count(self) -> int:
        return sum(1 for item in self.items if item.created_candidate_id is not None)


def _source_family(company_key: str) -> str:
    return company_key.strip().lower().replace(" ", "_")


def _source_name_candidate(company_key: str) -> str:
    return f"{_source_family(company_key)}:discovery"


def decide_candidate_promotion_item(item: CandidateExpansionItem) -> CandidatePromotionItem:
    """Turn one candidate-expansion item into a promotion-gate decision."""

    if item.known_candidate_id is not None or item.decision in SKIPPED_PROMOTION_DECISIONS:
        promotion_decision = "promotion_skipped_existing"
        risk_level = "low"
        reason = "company already exists in employer-origin candidate lifecycle"
        next_action = "Route evidence to the existing candidate instead of creating a duplicate"
    elif item.decision in DIRECT_PROMOTION_DECISIONS:
        promotion_decision = "promotion_recommended"
        risk_level = "unknown"
        reason = "candidate expansion recommends modeling this company for origin-source discovery"
        next_action = "Create discovery candidate, then run Origin Source Discovery Gate"
    elif item.decision in MANUAL_PROMOTION_DECISIONS:
        promotion_decision = "promotion_manual_review_required"
        risk_level = "medium"
        reason = "candidate expansion requires source-role or evidence review before promotion"
        next_action = "Review manually before creating an employer-origin candidate"
    elif item.decision in REJECTED_PROMOTION_DECISIONS:
        promotion_decision = "promotion_rejected_noise"
        risk_level = "blocked"
        reason = "candidate expansion classifies this item as market noise"
        next_action = "Do not create candidate unless future evidence changes the review decision"
    else:
        promotion_decision = "promotion_deferred"
        risk_level = "unknown"
        reason = "candidate expansion evidence is insufficient for candidate creation"
        next_action = "Wait for more observations or stronger evidence before promotion"

    family = _source_family(item.company_key)
    return CandidatePromotionItem(
        candidate_expansion_item_id=item.item_id,
        candidate_expansion_review_id=item.review_id,
        company_key=item.company_key,
        company_name=item.company_name,
        source_name=item.source_name,
        source_decision=item.decision,
        promotion_decision=promotion_decision,
        priority=item.priority,
        evidence_count=item.evidence_count,
        source_name_candidate=_source_name_candidate(item.company_key),
        source_family_candidate=family,
        source_target_candidate=None,
        source_type_candidate="employer_origin_career_site",
        candidate_url=None,
        risk_level=risk_level,
        reason=reason,
        recommended_next_action=next_action,
        evidence={
            "candidate_expansion_reason": item.reason,
            "candidate_expansion_next_action": item.recommended_next_action,
            "known_candidate_id": item.known_candidate_id,
            "known_candidate_status": item.known_candidate_status,
            "source_evidence": item.evidence,
        },
    )


def build_candidate_promotion_review(
    items: Iterable[CandidateExpansionItem],
    *,
    candidate_expansion_review_id: int,
    company_key_filter: str | None = None,
) -> CandidatePromotionReview:
    """Build a deterministic promotion review for one expansion review."""

    normalized_filter = company_key_filter.strip().lower() if company_key_filter else None
    decisions = []
    for item in items:
        if normalized_filter and item.company_key.lower() != normalized_filter:
            continue
        decisions.append(decide_candidate_promotion_item(item))
    decisions.sort(
        key=lambda item: (
            {
                "promotion_recommended": 1,
                "promotion_manual_review_required": 2,
                "promotion_deferred": 3,
                "promotion_rejected_noise": 4,
                "promotion_skipped_existing": 5,
            }.get(item.promotion_decision, 9),
            -item.priority,
            -item.evidence_count,
            item.company_name.lower(),
        )
    )
    return CandidatePromotionReview(
        candidate_expansion_review_id=candidate_expansion_review_id,
        items=tuple(decisions),
    )
