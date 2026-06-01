from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from src.search_intelligence.candidate_intelligence import CandidateSkill, validate_skill


NOISE_TERMS = {
    "genders", "mitarbeiter", "mitarbeiterin", "services", "service", "public",
    "modern", "moderne", "projekte", "projekt", "team", "master", "kunden",
    "kunde", "bereich", "schwerpunkt", "gestütztes", "kaufmännischer",
    "sachbearbeiter", "firmenkunden", "bankwesen",
}

TERM_SKILL_ALIASES = {
    "analytics": "Analytics",
    "analyse": "Analytics",
    "analysis": "Analytics",
    "data": "Data Modeling",
    "daten": "Data Modeling",
    "datenarchitekt": "Data Modeling",
    "platform": "Cloud Data Platforms",
    "plattform": "Cloud Data Platforms",
    "cloud": "Cloud Data Platforms",
    "azure": "Azure",
    "aws": "Cloud Data Platforms",
    "gcp": "Cloud Data Platforms",
    "python": "Python",
    "sql": "SQL",
    "postgresql": "PostgreSQL",
    "databricks": "Databricks",
    "spark": "Spark",
    "kafka": "Kafka",
    "bi": "Business Intelligence",
    "business intelligence": "Business Intelligence",
    "etl": "ETL Pipelines",
    "elt": "ETL Pipelines",
    "pipeline": "ETL Pipelines",
    "pipelines": "ETL Pipelines",
    "streaming": "Kafka",
    "requirements": "Requirements Engineering",
    "anforderungen": "Requirements Engineering",
    "product": "Product Ownership",
    "produkt": "Product Ownership",
    "scrum": "Scrum",
    "safe": "SAFe",
    "ai": "Machine Learning",
    "ki": "Machine Learning",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "devops": "CI/CD",
    "ci": "CI/CD",
    "cd": "CI/CD",
}


@dataclass(frozen=True)
class VocabularySignalInput:
    observed_term: str
    company_count: int
    observation_count: int


@dataclass(frozen=True)
class VocabularySignalScore:
    observed_term: str
    company_count: int
    observation_count: int
    noise_penalty: int
    signal_score: Decimal


@dataclass(frozen=True)
class SearchTermValueScore:
    observed_term: str
    profile_name: str
    profile_version: str
    matched_skill_name: str | None
    matched_skill_category: str | None
    vocabulary_signal_score: Decimal
    career_direction_score: Decimal
    capability_alignment_score: Decimal
    growth_gap_score: Decimal
    overall_value_score: Decimal
    value_band: str


def _decimal(value: float | int | Decimal) -> Decimal:
    return Decimal(str(round(float(value), 2)))


def noise_penalty_for_term(term: str) -> int:
    normalized = term.strip().lower()
    if normalized in NOISE_TERMS:
        return 85
    if len(normalized) <= 2 and normalized not in {"ai", "bi", "ml", "ki", "qa"}:
        return 60
    if normalized.isdigit():
        return 90
    return 0


def score_vocabulary_signal(item: VocabularySignalInput) -> VocabularySignalScore:
    if not item.observed_term.strip():
        raise ValueError("observed_term must not be empty")
    if item.company_count < 0:
        raise ValueError("company_count must not be negative")
    if item.observation_count < 0:
        raise ValueError("observation_count must not be negative")

    company_component = min(50.0, math.log1p(item.company_count) * 18.0)
    observation_component = min(50.0, math.log1p(item.observation_count) * 14.0)
    penalty = noise_penalty_for_term(item.observed_term)
    score = max(0.0, min(100.0, company_component + observation_component - penalty))
    return VocabularySignalScore(
        observed_term=item.observed_term.strip().lower(),
        company_count=item.company_count,
        observation_count=item.observation_count,
        noise_penalty=penalty,
        signal_score=_decimal(score),
    )


def build_vocabulary_signal_scores(items: list[VocabularySignalInput]) -> list[VocabularySignalScore]:
    return sorted(
        (score_vocabulary_signal(item) for item in items),
        key=lambda item: (item.signal_score, item.company_count, item.observation_count, item.observed_term),
        reverse=True,
    )


def match_skill_for_term(term: str, skills: list[CandidateSkill] | tuple[CandidateSkill, ...]) -> CandidateSkill | None:
    normalized = term.strip().lower()
    target_skill_name = TERM_SKILL_ALIASES.get(normalized)
    normalized_skill_map = {skill.skill_name.strip().lower(): validate_skill(skill) for skill in skills}
    if target_skill_name:
        return normalized_skill_map.get(target_skill_name.strip().lower())

    for skill in skills:
        validated = validate_skill(skill)
        if normalized == validated.skill_name.strip().lower():
            return validated
    return None


def value_band(score: Decimal) -> str:
    numeric = float(score)
    if numeric >= 85:
        return "strategic"
    if numeric >= 70:
        return "high"
    if numeric >= 45:
        return "medium"
    return "low"


def score_search_term_value(
    signal: VocabularySignalScore,
    *,
    profile_name: str,
    profile_version: str,
    skills: list[CandidateSkill] | tuple[CandidateSkill, ...],
) -> SearchTermValueScore:
    skill = match_skill_for_term(signal.observed_term, skills)
    if skill is None:
        career_direction = Decimal("35.00")
        capability = Decimal("0.00")
        growth_gap = Decimal("0.00")
        matched_name = None
        matched_category = None
    else:
        career_direction = Decimal(str(skill.career_direction_weight))
        capability = Decimal(str(skill.capability_score))
        growth_gap = Decimal(str(skill.growth_gap))
        matched_name = skill.skill_name
        matched_category = skill.skill_category

    overall = (
        float(signal.signal_score) * 0.40
        + float(career_direction) * 0.40
        + float(capability) * 0.10
        + float(growth_gap) * 0.10
    )
    overall_score = _decimal(max(0.0, min(100.0, overall)))
    return SearchTermValueScore(
        observed_term=signal.observed_term,
        profile_name=profile_name,
        profile_version=profile_version,
        matched_skill_name=matched_name,
        matched_skill_category=matched_category,
        vocabulary_signal_score=signal.signal_score,
        career_direction_score=_decimal(career_direction),
        capability_alignment_score=_decimal(capability),
        growth_gap_score=_decimal(growth_gap),
        overall_value_score=overall_score,
        value_band=value_band(overall_score),
    )


def build_search_term_value_scores(
    signals: list[VocabularySignalScore],
    *,
    profile_name: str,
    profile_version: str,
    skills: list[CandidateSkill] | tuple[CandidateSkill, ...],
) -> list[SearchTermValueScore]:
    return sorted(
        (
            score_search_term_value(
                signal,
                profile_name=profile_name,
                profile_version=profile_version,
                skills=skills,
            )
            for signal in signals
        ),
        key=lambda item: (item.overall_value_score, item.vocabulary_signal_score, item.observed_term),
        reverse=True,
    )
