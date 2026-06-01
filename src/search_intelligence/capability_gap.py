from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.search_intelligence.candidate_intelligence import CandidateSkill, validate_skill


@dataclass(frozen=True)
class SearchTermSupport:
    observed_term: str
    matched_skill_name: str
    overall_value_score: Decimal
    value_band: str


@dataclass(frozen=True)
class CapabilityGapScore:
    profile_name: str
    profile_version: str
    skill_name: str
    skill_category: str
    capability_score: int
    career_direction_weight: int
    growth_gap: int
    supporting_terms: tuple[str, ...]
    max_search_term_value: Decimal
    avg_search_term_value: Decimal
    market_signal_score: Decimal
    priority_score: Decimal
    priority_band: str
    recommendation: str


def _decimal(value: float | int | Decimal) -> Decimal:
    return Decimal(str(round(float(value), 2)))


def _band(score: Decimal) -> str:
    value = float(score)
    if value >= 80:
        return "critical"
    if value >= 65:
        return "high"
    if value >= 40:
        return "medium"
    return "low"


def _recommendation(score: Decimal, skill: CandidateSkill) -> str:
    value = float(score)
    if value >= 80 and skill.career_direction_weight >= 90:
        return "certification_candidate"
    if value >= 65:
        return "prioritize_learning"
    if value >= 40:
        return "practice_in_project"
    return "monitor"


def score_capability_gap(
    *,
    profile_name: str,
    profile_version: str,
    skill: CandidateSkill,
    supports: list[SearchTermSupport],
) -> CapabilityGapScore:
    skill = validate_skill(skill)
    growth_gap = skill.growth_gap

    if supports:
        values = [float(item.overall_value_score) for item in supports]
        max_value = max(values)
        avg_value = sum(values) / len(values)
        market_signal = min(100.0, (max_value * 0.65) + (avg_value * 0.25) + min(10.0, len(supports) * 2.0))
    else:
        max_value = 0.0
        avg_value = 0.0
        market_signal = 0.0

    priority = (
        growth_gap * 0.45
        + skill.career_direction_weight * 0.25
        + market_signal * 0.30
    )
    score = _decimal(min(100.0, priority))
    terms = tuple(item.observed_term for item in sorted(supports, key=lambda item: item.overall_value_score, reverse=True)[:8])
    return CapabilityGapScore(
        profile_name=profile_name,
        profile_version=profile_version,
        skill_name=skill.skill_name,
        skill_category=skill.skill_category,
        capability_score=skill.capability_score,
        career_direction_weight=skill.career_direction_weight,
        growth_gap=growth_gap,
        supporting_terms=terms,
        max_search_term_value=_decimal(max_value),
        avg_search_term_value=_decimal(avg_value),
        market_signal_score=_decimal(market_signal),
        priority_score=score,
        priority_band=_band(score),
        recommendation=_recommendation(score, skill),
    )


def build_capability_gap_scores(
    *,
    profile_name: str,
    profile_version: str,
    skills: list[CandidateSkill] | tuple[CandidateSkill, ...],
    term_supports: list[SearchTermSupport],
) -> list[CapabilityGapScore]:
    supports_by_skill: dict[str, list[SearchTermSupport]] = {}
    for support in term_supports:
        supports_by_skill.setdefault(support.matched_skill_name, []).append(support)

    scores = [
        score_capability_gap(
            profile_name=profile_name,
            profile_version=profile_version,
            skill=skill,
            supports=supports_by_skill.get(skill.skill_name, []),
        )
        for skill in skills
        if skill.career_direction_weight >= 60 or skill.growth_gap >= 30
    ]
    return sorted(
        scores,
        key=lambda item: (item.priority_score, item.market_signal_score, item.growth_gap, item.skill_name),
        reverse=True,
    )
