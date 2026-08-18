"""Deterministic, source-neutral evidence rubric for Product V1 ranking factors.

The approved Product V1 policy already owns factor weights, the 70-point minimum,
Top-5 no-fill semantics and the comparable-score tie-break. This module does not
change those product decisions. It only derives the four pre-existing component
scores from explicit employer-origin job evidence using a transparent generic
rubric.

No model, Candidate Fact, hard-filter, rank, Top-5, persistence or product
authority is created here. Missing signals score as missing fit evidence rather
than being guessed from company/title prestige or outside knowledge.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Iterable

from src.search_intelligence.product_v1_assessment_evidence import (
    ProductV1AssessmentEvidence,
    normalize_job_text,
)

RUBRIC_VERSION = "product-v1-ranking-evidence-v1"


@dataclass(frozen=True)
class RankingSignalReference:
    factor: str
    signal: str
    source_surface: str
    evidence: str
    span_start: int
    span_end: int
    points: float

    def canonical_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProductV1RankingEvidence:
    profile_direction_score: float
    data_focus_score: float
    reliability_focus_score: float
    evidence_quality_score: float
    references: tuple[RankingSignalReference, ...]
    explanations: tuple[str, ...]
    uncertainties: tuple[str, ...]
    rubric_version: str = RUBRIC_VERSION
    ranking_authority: bool = False
    product_authority: bool = False

    def ranking_scores_patch(self) -> dict[str, float]:
        return {
            "profile_direction_score": self.profile_direction_score,
            "data_focus_score": self.data_focus_score,
            "reliability_focus_score": self.reliability_focus_score,
            "evidence_quality_score": self.evidence_quality_score,
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            **self.ranking_scores_patch(),
            "rubric_version": self.rubric_version,
            "references": [reference.canonical_payload() for reference in self.references],
            "explanations": list(self.explanations),
            "uncertainties": list(self.uncertainties),
            "ranking_authority": self.ranking_authority,
            "product_authority": self.product_authority,
        }


@dataclass(frozen=True)
class _SignalRule:
    signal: str
    points: float
    pattern: re.Pattern[str]


_PROFILE_TITLE_RULES = (
    _SignalRule(
        "machine_learning_role",
        100.0,
        re.compile(
            r"\b(?:machine learning|ml|ai|artificial intelligence|mlops)\s+"
            r"(?:engineer|developer|specialist|architect)\b",
            re.IGNORECASE,
        ),
    ),
    _SignalRule(
        "data_engineering_role",
        85.0,
        re.compile(r"\b(?:data|analytics)\s+engineer\b", re.IGNORECASE),
    ),
    _SignalRule(
        "data_science_role",
        80.0,
        re.compile(r"\bdata scientist\b", re.IGNORECASE),
    ),
    _SignalRule(
        "software_engineering_role",
        65.0,
        re.compile(r"\bsoftware\s+(?:engineer|developer)\b", re.IGNORECASE),
    ),
)

_PROFILE_SUPPORT_RULES = (
    _SignalRule("machine_learning", 3.0, re.compile(r"\bmachine learning\b", re.IGNORECASE)),
    _SignalRule("mlops", 3.0, re.compile(r"\bmlops\b", re.IGNORECASE)),
    _SignalRule("generative_ai", 3.0, re.compile(r"\b(?:generative ai|genai)\b", re.IGNORECASE)),
    _SignalRule("large_language_models", 3.0, re.compile(r"\b(?:llms?|large language models?)\b", re.IGNORECASE)),
    _SignalRule("ml_frameworks", 3.0, re.compile(r"\b(?:pytorch|tensorflow|scikit-learn)\b", re.IGNORECASE)),
)

_DATA_TITLE_RULES = (
    _SignalRule(
        "data_role_title",
        20.0,
        re.compile(r"\b(?:data|analytics)\s+engineer\b", re.IGNORECASE),
    ),
)

_DATA_DESCRIPTION_RULES = (
    _SignalRule("data_pipelines", 15.0, re.compile(r"\bdata\s+pipelines?\b", re.IGNORECASE)),
    _SignalRule("sql", 15.0, re.compile(r"\bsql\b", re.IGNORECASE)),
    _SignalRule("distributed_data", 15.0, re.compile(r"\b(?:spark|pyspark)\b", re.IGNORECASE)),
    _SignalRule("databricks", 15.0, re.compile(r"\bdatabricks\b", re.IGNORECASE)),
    _SignalRule("warehouse_lakehouse", 15.0, re.compile(r"\b(?:data warehouse|data lake|lakehouse|snowflake)\b", re.IGNORECASE)),
    _SignalRule("etl_elt", 15.0, re.compile(r"\b(?:etl|elt)\b", re.IGNORECASE)),
)

_RELIABILITY_RULES = (
    _SignalRule("reliability", 20.0, re.compile(r"\b(?:reliability|site reliability|sre)\b", re.IGNORECASE)),
    _SignalRule("testing_quality", 20.0, re.compile(r"\b(?:automated testing|test automation|quality engineering|quality assurance)\b", re.IGNORECASE)),
    _SignalRule("observability", 20.0, re.compile(r"\b(?:observability|monitoring|telemetry|alerting)\b", re.IGNORECASE)),
    _SignalRule("ci_cd", 20.0, re.compile(r"\b(?:ci/cd|continuous integration|continuous delivery|continuous deployment)\b", re.IGNORECASE)),
    _SignalRule("production_operations", 20.0, re.compile(r"\b(?:production systems?|production workloads?|operational excellence|incident response)\b", re.IGNORECASE)),
    _SignalRule("automation_iac", 20.0, re.compile(r"\b(?:infrastructure as code|terraform|automation)\b", re.IGNORECASE)),
)


def _first_match(text: str, rule: _SignalRule) -> re.Match[str] | None:
    return rule.pattern.search(text)


def _reference(
    *,
    factor: str,
    rule: _SignalRule,
    source_surface: str,
    match: re.Match[str],
) -> RankingSignalReference:
    if source_surface not in {"title", "description"}:
        raise ValueError(f"unsupported ranking evidence surface: {source_surface}")
    return RankingSignalReference(
        factor=factor,
        signal=rule.signal,
        source_surface=source_surface,
        evidence=match.group(0),
        span_start=match.start(),
        span_end=match.end(),
        points=rule.points,
    )


def _additive_score(
    *,
    factor: str,
    text: str,
    source_surface: str,
    rules: Iterable[_SignalRule],
) -> tuple[float, list[RankingSignalReference]]:
    score = 0.0
    references: list[RankingSignalReference] = []
    for rule in rules:
        match = _first_match(text, rule)
        if match is None:
            continue
        score += rule.points
        references.append(
            _reference(
                factor=factor,
                rule=rule,
                source_surface=source_surface,
                match=match,
            )
        )
    return min(100.0, round(score, 2)), references


def _profile_score(
    *, title: str, text: str
) -> tuple[float, list[RankingSignalReference]]:
    title_references: list[RankingSignalReference] = []
    base = 0.0
    for rule in _PROFILE_TITLE_RULES:
        match = _first_match(title, rule)
        if match is None:
            continue
        if rule.points > base:
            base = rule.points
            title_references = [
                _reference(
                    factor="profile_direction",
                    rule=rule,
                    source_surface="title",
                    match=match,
                )
            ]
    support, support_references = _additive_score(
        factor="profile_direction",
        text=text,
        source_surface="description",
        rules=_PROFILE_SUPPORT_RULES,
    )
    if base == 0.0 and support > 0:
        base = 50.0
    return min(100.0, round(base + support, 2)), [
        *title_references,
        *support_references,
    ]


def _data_score(
    *, title: str, text: str
) -> tuple[float, list[RankingSignalReference]]:
    title_score, title_references = _additive_score(
        factor="data_focus",
        text=title,
        source_surface="title",
        rules=_DATA_TITLE_RULES,
    )
    description_score, description_references = _additive_score(
        factor="data_focus",
        text=text,
        source_surface="description",
        rules=_DATA_DESCRIPTION_RULES,
    )
    return min(100.0, round(title_score + description_score, 2)), [
        *title_references,
        *description_references,
    ]


def _evidence_quality_score(
    *,
    origin_validation_status: str,
    activity_status: str,
    assessment: ProductV1AssessmentEvidence,
) -> tuple[float, tuple[str, ...]]:
    score = 10.0  # bounded employer-origin detail text is present by construction.
    uncertainties: list[str] = []

    if origin_validation_status == "validated":
        score += 40.0
    else:
        uncertainties.append("origin_validation_not_confirmed")

    if activity_status == "active":
        score += 20.0
    else:
        uncertainties.append("current_activity_not_confirmed")

    resolved = 0
    if assessment.employment_type != "unknown":
        resolved += 1
    if assessment.required_languages:
        resolved += 1
    if assessment.weekly_hours_min is not None or assessment.weekly_hours_max is not None:
        resolved += 1
    if assessment.work_model != "unknown":
        resolved += 1
    if assessment.requirements_seniority != "unknown":
        resolved += 1
    score += resolved * 6.0
    if resolved < 5:
        uncertainties.append(f"assessment_evidence_incomplete:{resolved}/5")
    return min(100.0, round(score, 2)), tuple(uncertainties)


def build_product_v1_ranking_evidence(
    *,
    title: str,
    description: object,
    origin_validation_status: str,
    activity_status: str,
    assessment_evidence: ProductV1AssessmentEvidence,
) -> ProductV1RankingEvidence:
    """Build transparent factor scores without assigning rank or Top-5 authority."""

    if not isinstance(title, str) or not title.strip():
        raise ValueError("job title is missing")
    canonical_title = title.strip()
    text = normalize_job_text(description)

    profile_score, profile_refs = _profile_score(title=canonical_title, text=text)
    data_score, data_refs = _data_score(title=canonical_title, text=text)
    reliability_score, reliability_refs = _additive_score(
        factor="reliability_focus",
        text=text,
        source_surface="description",
        rules=_RELIABILITY_RULES,
    )
    evidence_score, uncertainties = _evidence_quality_score(
        origin_validation_status=origin_validation_status,
        activity_status=activity_status,
        assessment=assessment_evidence,
    )

    references = tuple([*profile_refs, *data_refs, *reliability_refs])
    explanations = (
        "Profile direction uses explicit role/title and ML/AI evidence only.",
        "Data focus is additive across distinct explicit data-engineering signal families.",
        "Reliability focus is additive across distinct explicit reliability/quality/operations signal families.",
        "Evidence quality reflects employer-origin/current-activity authority plus deterministic assessment coverage.",
    )
    return ProductV1RankingEvidence(
        profile_direction_score=profile_score,
        data_focus_score=data_score,
        reliability_focus_score=reliability_score,
        evidence_quality_score=evidence_score,
        references=references,
        explanations=explanations,
        uncertainties=uncertainties,
    )


__all__ = [
    "RUBRIC_VERSION",
    "ProductV1RankingEvidence",
    "RankingSignalReference",
    "build_product_v1_ranking_evidence",
]
