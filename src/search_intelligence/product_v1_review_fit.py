"""Deterministic review-fit preview for jobs without authoritative Product V1 scores.

The score is an operator-orientation surface only. It may help order the review
queue, but it has no ranking, Top-5, hard-filter, application or product authority.
It intentionally uses only already-projected role, geography and lifecycle signals;
operator relevance labels are never fed back into this score.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.search_intelligence.product_v1_contenders import (
    classify_geography,
    classify_role_title,
)


REVIEW_FIT_VERSION = "product-v1-review-fit/v1"


@dataclass(frozen=True)
class ReviewFitPreview:
    score: float
    role_family: str | None
    geography_bucket: str
    reasons: tuple[str, ...]
    score_scope: str = "review_preview"
    ranking_authority: bool = False
    top5_authority: bool = False
    application_authority: bool = False

    def canonical_payload(self) -> dict[str, object]:
        return {
            "score": self.score,
            "role_family": self.role_family,
            "geography_bucket": self.geography_bucket,
            "reasons": list(self.reasons),
            "score_scope": self.score_scope,
            "version": REVIEW_FIT_VERSION,
            "ranking_authority": self.ranking_authority,
            "top5_authority": self.top5_authority,
            "application_authority": self.application_authority,
        }


_PRIMARY_BASE = {
    "machine_learning_engineer": 86.0,
    "mlops": 88.0,
    "ml_platform": 88.0,
    "ai_platform": 86.0,
    "ai_engineer_probe": 82.0,
}
_BRIDGE_BASE = {
    "data_platform_engineer": 82.0,
    "data_engineer": 80.0,
    "analytics_engineer": 74.0,
}


def build_review_fit_preview(row: Mapping[str, object]) -> ReviewFitPreview:
    title = str(row.get("title") or "")
    role = classify_role_title(title)
    geography = classify_geography(dict(row))
    reasons: list[str] = []

    if not geography.eligible_for_bounded_pool:
        return ReviewFitPreview(
            score=0.0,
            role_family=role.family if role else None,
            geography_bucket=geography.bucket,
            reasons=("outside approved geography",),
        )

    if role is None:
        score = 30.0
        reasons.append("no canonical target-role title signal")
    elif role.family == "ai_ml_data_reliability":
        score = 88.0
        reasons.append("AI/ML/Data Reliability target signal")
    elif role.family in _PRIMARY_BASE:
        score = _PRIMARY_BASE[role.family]
        reasons.append(f"primary target role: {role.family}")
    elif role.family in _BRIDGE_BASE:
        score = _BRIDGE_BASE[role.family]
        reasons.append(f"data-engineering bridge role: {role.family}")
    else:
        score = 65.0
        reasons.append(f"adjacent target role: {role.family}")

    if role is not None and len(role.signals) > 1:
        bonus = min(6.0, 3.0 * (len(role.signals) - 1))
        score += bonus
        reasons.append(f"multi-signal role bonus +{bonus:.0f}")

    geography_bonus = {
        "hannover_explicit": 10.0,
        "germany_remote": 10.0,
        "commute_observed_acceptable": 8.0,
        "commute_or_geography_review_required": 2.0,
    }.get(geography.bucket, 0.0)
    score += geography_bonus
    if geography_bonus:
        reasons.append(f"geography {geography.bucket} +{geography_bonus:.0f}")

    lifecycle = str(row.get("lifecycle_status") or "")
    if lifecycle == "active_confirmed":
        score += 2.0
        reasons.append("current active +2")
    elif lifecycle == "stale_needs_refresh":
        score -= 8.0
        reasons.append("stale evidence -8")
    elif lifecycle == "inactive_confirmed":
        score -= 25.0
        reasons.append("inactive -25")

    return ReviewFitPreview(
        score=round(max(0.0, min(100.0, score)), 1),
        role_family=role.family if role else None,
        geography_bucket=geography.bucket,
        reasons=tuple(reasons),
    )


def enrich_review_fit(row: Mapping[str, object]) -> dict[str, object]:
    enriched = dict(row)
    preview = build_review_fit_preview(row)
    enriched["review_fit_score"] = preview.score
    enriched["review_fit"] = preview.canonical_payload()
    enriched["display_fit_score"] = (
        float(row["overall_quality_score"])
        if row.get("overall_quality_score") is not None
        else preview.score
    )
    enriched["display_fit_scope"] = (
        "authoritative_product_score"
        if row.get("overall_quality_score") is not None
        else "review_preview"
    )
    return enriched


__all__ = [
    "REVIEW_FIT_VERSION",
    "ReviewFitPreview",
    "build_review_fit_preview",
    "enrich_review_fit",
]
