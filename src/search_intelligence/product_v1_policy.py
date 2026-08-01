"""Approved Product V1 hard-filter policy and deterministic evaluation.

The policy evaluates evidence, not title labels alone. Salary remains a soft,
negotiable signal and never turns an otherwise suitable job into a hard failure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


_LANGUAGE_ALIASES = {
    "de": "de",
    "deutsch": "de",
    "german": "de",
    "en": "en",
    "englisch": "en",
    "english": "en",
}

_EMPLOYMENT_ALIASES = {
    "permanent": "permanent",
    "festanstellung": "permanent",
    "unbefristet": "permanent",
    "fixed_term": "fixed_term",
    "befristet": "fixed_term",
    "temporary": "temporary",
    "freelance": "freelance",
    "internship": "internship",
    "trainee": "trainee",
    "unknown": "unknown",
}

_SENIOR_REQUIREMENT_LEVELS = {"senior", "lead", "principal"}


@dataclass(frozen=True)
class HardFilterPolicy:
    status: str = "approved"
    permanent_employment_required: bool = True
    accepted_languages: frozenset[str] = field(
        default_factory=lambda: frozenset({"de", "en"})
    )
    weekly_hours_min: float = 35.0
    weekly_hours_max: float = 40.0
    salary_treatment: str = "soft_negotiable_target"
    target_salary_gross_eur: int = 75_000
    seniority_assessment_mode: str = "requirements_and_capability_fit_over_title"
    allow_senior_title_when_capability_fit: bool = True
    reject_junior_title_with_senior_requirements: bool = True
    unknown_required_evidence_action: str = "manual_review_required"
    policy_version: str = "product-v1-2026-08-02"

    def validate(self) -> None:
        if self.status != "approved":
            raise ValueError("Hard-filter policy must be operator-approved")
        if self.seniority_assessment_mode != "requirements_and_capability_fit_over_title":
            raise ValueError("Unsupported seniority assessment mode")
        if self.unknown_required_evidence_action != "manual_review_required":
            raise ValueError("Unknown required evidence must remain review-required")
        if not 0 <= self.weekly_hours_min <= self.weekly_hours_max <= 80:
            raise ValueError("Weekly-hours policy must be a valid range")
        if self.salary_treatment != "soft_negotiable_target":
            raise ValueError("Salary must remain a soft negotiable target")
        if self.target_salary_gross_eur <= 0:
            raise ValueError("Salary target must be positive")
        if not self.accepted_languages:
            raise ValueError("At least one accepted language is required")


@dataclass(frozen=True)
class JobConstraintEvidence:
    employment_type: str = "unknown"
    employment_evidence_status: str = "unknown"
    required_languages: tuple[str, ...] = ()
    language_evidence_status: str = "unknown"
    weekly_hours_min: float | None = None
    weekly_hours_max: float | None = None
    weekly_hours_evidence_status: str = "unknown"
    salary_min_gross_eur: int | None = None
    salary_max_gross_eur: int | None = None
    salary_evidence_status: str = "unknown"
    title_seniority: str = "unknown"
    requirements_seniority: str = "unknown"
    capability_fit_status: str = "unknown"
    seniority_evidence_status: str = "unknown"


@dataclass(frozen=True)
class HardFilterEvaluation:
    status: str
    employment_status: str
    language_status: str
    weekly_hours_status: str
    seniority_status: str
    salary_signal: str
    reasons: tuple[str, ...]
    policy_version: str


def _normalized_languages(values: Iterable[str]) -> frozenset[str]:
    normalized: set[str] = set()
    for value in values:
        raw = value.strip().lower()
        if raw:
            normalized.add(_LANGUAGE_ALIASES.get(raw, raw))
    return frozenset(normalized)


def _employment_status(evidence: JobConstraintEvidence, policy: HardFilterPolicy) -> str:
    if evidence.employment_evidence_status != "observed":
        return "manual_review_required"
    normalized = _EMPLOYMENT_ALIASES.get(
        evidence.employment_type.strip().lower(),
        evidence.employment_type.strip().lower(),
    )
    if policy.permanent_employment_required and normalized != "permanent":
        return "failed"
    return "passed"


def _language_status(evidence: JobConstraintEvidence, policy: HardFilterPolicy) -> str:
    if evidence.language_evidence_status != "observed":
        return "manual_review_required"
    required = _normalized_languages(evidence.required_languages)
    return "passed" if required.issubset(policy.accepted_languages) else "failed"


def _weekly_hours_status(evidence: JobConstraintEvidence, policy: HardFilterPolicy) -> str:
    if evidence.weekly_hours_evidence_status != "observed":
        return "manual_review_required"
    if evidence.weekly_hours_min is None and evidence.weekly_hours_max is None:
        return "manual_review_required"
    job_min = (
        evidence.weekly_hours_min
        if evidence.weekly_hours_min is not None
        else evidence.weekly_hours_max
    )
    job_max = (
        evidence.weekly_hours_max
        if evidence.weekly_hours_max is not None
        else evidence.weekly_hours_min
    )
    assert job_min is not None and job_max is not None
    return (
        "passed"
        if job_min <= policy.weekly_hours_max and job_max >= policy.weekly_hours_min
        else "failed"
    )


def _seniority_status(evidence: JobConstraintEvidence, policy: HardFilterPolicy) -> str:
    if evidence.capability_fit_status == "failed":
        return "failed"
    if evidence.capability_fit_status != "passed":
        return "manual_review_required"

    title = evidence.title_seniority.strip().lower()
    requirements = evidence.requirements_seniority.strip().lower()
    if (
        policy.reject_junior_title_with_senior_requirements
        and title == "junior"
        and requirements in _SENIOR_REQUIREMENT_LEVELS
    ):
        return "failed"

    # A Senior/Lead/Principal title is not a hard blocker when the actual
    # requirements and the operator's evidenced capabilities fit.
    return "passed"


def _salary_signal(evidence: JobConstraintEvidence, policy: HardFilterPolicy) -> str:
    if evidence.salary_evidence_status == "unknown":
        return "unknown"
    if evidence.salary_evidence_status == "negotiable":
        return "negotiable"
    if (
        evidence.salary_max_gross_eur is not None
        and evidence.salary_max_gross_eur < policy.target_salary_gross_eur
    ):
        return "below_target_review"
    observed_reference = (
        evidence.salary_max_gross_eur
        if evidence.salary_max_gross_eur is not None
        else evidence.salary_min_gross_eur
    )
    if observed_reference is not None and observed_reference >= policy.target_salary_gross_eur:
        return "at_or_above_target"
    return "around_target_or_incomplete"


def evaluate_hard_filters(
    evidence: JobConstraintEvidence,
    policy: HardFilterPolicy | None = None,
) -> HardFilterEvaluation:
    """Evaluate the approved hard filters without guessing missing evidence."""
    effective_policy = policy or HardFilterPolicy()
    effective_policy.validate()

    employment = _employment_status(evidence, effective_policy)
    languages = _language_status(evidence, effective_policy)
    weekly_hours = _weekly_hours_status(evidence, effective_policy)
    seniority = _seniority_status(evidence, effective_policy)
    salary = _salary_signal(evidence, effective_policy)

    required_statuses = (employment, languages, weekly_hours, seniority)
    if "failed" in required_statuses:
        status = "failed"
    elif "manual_review_required" in required_statuses:
        status = "unknown"
    else:
        status = "passed"

    reasons = (
        f"employment:{employment}",
        f"languages:{languages}",
        f"weekly_hours:{weekly_hours}",
        f"seniority_and_capability_fit:{seniority}",
        f"salary_soft_signal:{salary}",
    )
    return HardFilterEvaluation(
        status=status,
        employment_status=employment,
        language_status=languages,
        weekly_hours_status=weekly_hours,
        seniority_status=seniority,
        salary_signal=salary,
        reasons=reasons,
        policy_version=effective_policy.policy_version,
    )
