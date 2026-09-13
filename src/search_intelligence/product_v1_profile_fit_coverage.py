"""Fail-closed F4A Candidate<->Job Profile Fit coverage.

This module creates no ranking score and never treats the preliminary review-fit
preview as Candidate<->Job truth. Candidate-side capability authority comes only
from an exact, current Candidate Fact capability review supplied by the Product
query. Geography/work-model/commute preferences come only from approved
``operator_preference`` Candidate Facts, projected to this module as structured
non-secret tags.

Supported preference tags are intentionally small and deterministic:

- ``profile-fit.city.<token>``
- ``profile-fit.country.<token>``
- ``profile-fit.work-model.remote|hybrid|onsite``
- ``profile-fit.commute.max-<minutes>``

The Product API receives only factor statuses and generic reason codes; Candidate
Fact statements, provenance references and raw preference-tag values are never
emitted.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping


PROFILE_FIT_VERSION = "product-v1-profile-fit-coverage/v1"
PROFILE_FIT_COMPLETE = "profile_fit_complete"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"
PASSED = "passed"
FAILED = "failed"
UNKNOWN = "unknown"

_COMMUTE_TAG = re.compile(r"^profile-fit\.commute\.max-(\d{1,3})$")
_CITY_PREFIX = "profile-fit.city."
_COUNTRY_PREFIX = "profile-fit.country."
_WORK_MODEL_PREFIX = "profile-fit.work-model."
_ALLOWED_WORK_MODELS = frozenset({"remote", "hybrid", "onsite"})


@dataclass(frozen=True)
class CandidateGeographyPolicy:
    cities: frozenset[str]
    countries: frozenset[str]
    work_models: frozenset[str]
    commute_max_minutes: int | None
    configured_dimensions: tuple[str, ...]
    valid: bool


@dataclass(frozen=True)
class FactorResult:
    status: str
    reason: str

    def payload(self) -> dict[str, str]:
        return {"status": self.status, "reason": self.reason}


def _token(value: object) -> str:
    text = str(value or "").strip().casefold()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _country_token(value: object) -> str:
    token = _token(value)
    if token in {"de", "deu", "deutschland", "germany"}:
        return "de"
    return token


def parse_candidate_geography_policy(tags: Iterable[str]) -> CandidateGeographyPolicy:
    cities: set[str] = set()
    countries: set[str] = set()
    work_models: set[str] = set()
    commute_values: set[int] = set()

    for raw in tags:
        tag = str(raw).strip().casefold()
        if tag.startswith(_CITY_PREFIX):
            value = _token(tag[len(_CITY_PREFIX) :])
            if value:
                cities.add(value)
            continue
        if tag.startswith(_COUNTRY_PREFIX):
            value = _country_token(tag[len(_COUNTRY_PREFIX) :])
            if value:
                countries.add(value)
            continue
        if tag.startswith(_WORK_MODEL_PREFIX):
            value = _token(tag[len(_WORK_MODEL_PREFIX) :])
            if value in _ALLOWED_WORK_MODELS:
                work_models.add(value)
            continue
        commute = _COMMUTE_TAG.fullmatch(tag)
        if commute:
            value = int(commute.group(1))
            if 0 <= value <= 240:
                commute_values.add(value)

    dimensions: list[str] = []
    if cities or countries:
        dimensions.append("geography")
    if work_models:
        dimensions.append("work_model")
    if commute_values:
        dimensions.append("commute")

    return CandidateGeographyPolicy(
        cities=frozenset(cities),
        countries=frozenset(countries),
        work_models=frozenset(work_models),
        commute_max_minutes=(next(iter(commute_values)) if len(commute_values) == 1 else None),
        configured_dimensions=tuple(dimensions),
        valid=bool(dimensions) and len(commute_values) <= 1,
    )


def _geography_factor(
    row: Mapping[str, object],
    policy: CandidateGeographyPolicy,
) -> FactorResult:
    if not policy.valid:
        return FactorResult(UNKNOWN, "approved_candidate_geography_preference_missing_or_ambiguous")

    missing = False
    failed = False

    if policy.cities:
        city = _token(row.get("city"))
        if not city:
            missing = True
        elif city not in policy.cities:
            failed = True
    elif policy.countries:
        country = _country_token(row.get("country"))
        if not country:
            missing = True
        elif country not in policy.countries:
            failed = True

    if policy.work_models:
        work_model = _token(row.get("work_model"))
        if not work_model or work_model == "unknown":
            missing = True
        elif work_model not in policy.work_models:
            failed = True

    if policy.commute_max_minutes is not None:
        commute = row.get("commute_minutes")
        if not isinstance(commute, int):
            missing = True
        elif commute > policy.commute_max_minutes:
            failed = True

    if failed:
        return FactorResult(FAILED, "candidate_geography_boundary_conflict")
    if missing:
        return FactorResult(UNKNOWN, "job_geography_work_model_or_commute_evidence_missing")
    return FactorResult(PASSED, "approved_candidate_geography_policy_matches_job_evidence")


def _capability_factor(row: Mapping[str, object]) -> FactorResult:
    if row.get("profile_fit_capability_review_exact") is not True:
        return FactorResult(UNKNOWN, "exact_current_candidate_fact_capability_review_missing")
    decision = str(row.get("profile_fit_capability_review_decision") or "").strip().casefold()
    if decision == PASSED:
        return FactorResult(PASSED, "exact_current_candidate_fact_capability_review_passed")
    if decision == FAILED:
        return FactorResult(FAILED, "exact_current_candidate_fact_capability_review_failed")
    return FactorResult(UNKNOWN, "exact_current_candidate_fact_capability_review_invalid")


def _hard_filter_component(row: Mapping[str, object], key: str) -> str:
    reasons = row.get("hard_filter_reasons")
    if not isinstance(reasons, Mapping):
        return UNKNOWN
    value = str(reasons.get(key) or "").strip().casefold()
    return value if value in {PASSED, FAILED, "manual_review_required"} else UNKNOWN


def _seniority_factor(row: Mapping[str, object], capability: FactorResult) -> FactorResult:
    if capability.status == FAILED:
        return FactorResult(FAILED, "capability_review_is_negative")
    if capability.status != PASSED:
        return FactorResult(UNKNOWN, "current_capability_evidence_required_for_seniority")
    value = _hard_filter_component(row, "seniority_and_capability_fit")
    if value == PASSED:
        return FactorResult(PASSED, "seniority_requirements_and_capability_fit_passed")
    if value == FAILED:
        return FactorResult(FAILED, "seniority_requirements_and_capability_fit_failed")
    return FactorResult(UNKNOWN, "seniority_requirement_evidence_missing")


def _hard_requirements_factor(
    row: Mapping[str, object],
    capability: FactorResult,
) -> FactorResult:
    components = tuple(
        _hard_filter_component(row, key)
        for key in ("employment", "languages", "weekly_hours")
    )
    if FAILED in components:
        return FactorResult(FAILED, "deterministic_hard_requirement_failed")

    hard_filter_status = str(row.get("hard_filter_status") or "").strip().casefold()
    if hard_filter_status == FAILED and capability.status == PASSED:
        return FactorResult(FAILED, "current_hard_filter_failed")
    if hard_filter_status == PASSED and capability.status == PASSED:
        return FactorResult(PASSED, "current_hard_filter_passed")
    if all(value == PASSED for value in components) and capability.status == PASSED:
        return FactorResult(PASSED, "deterministic_hard_requirements_passed")
    return FactorResult(UNKNOWN, "hard_requirement_evidence_missing")


def build_profile_fit_coverage(
    row: Mapping[str, object],
    *,
    candidate_preference_tags: Iterable[str] = (),
) -> dict[str, object]:
    """Return one conclusive F4A status or explicit insufficient evidence.

    A deterministic negative factor is conclusive even if another factor is
    unknown. A positive fit requires every required factor to be evidence-backed.
    """

    policy = parse_candidate_geography_policy(candidate_preference_tags)
    geography = _geography_factor(row, policy)
    capability = _capability_factor(row)
    seniority = _seniority_factor(row, capability)
    hard_requirements = _hard_requirements_factor(row, capability)
    factors = {
        "geography_work_model_commute": geography,
        "skills_capabilities": capability,
        "seniority": seniority,
        "hard_requirements": hard_requirements,
    }

    failed = tuple(name for name, factor in factors.items() if factor.status == FAILED)
    missing = tuple(name for name, factor in factors.items() if factor.status == UNKNOWN)

    if failed:
        coverage_status = PROFILE_FIT_COMPLETE
        decision = FAILED
        reason = "conclusive_negative_evidence"
    elif not missing and all(factor.status == PASSED for factor in factors.values()):
        coverage_status = PROFILE_FIT_COMPLETE
        decision = PASSED
        reason = "all_required_factors_evidence_backed"
    else:
        coverage_status = INSUFFICIENT_EVIDENCE
        decision = UNKNOWN
        reason = "required_factor_evidence_missing"

    return {
        "profile_fit_coverage_status": coverage_status,
        "profile_fit_decision": decision,
        "profile_fit_reason": reason,
        "profile_fit_version": PROFILE_FIT_VERSION,
        "profile_fit_factors": {
            name: factor.payload() for name, factor in factors.items()
        },
        "profile_fit_missing_factors": list(missing),
        "profile_fit_failed_factors": list(failed),
        "profile_fit_candidate_preference_dimensions": list(policy.configured_dimensions),
        "profile_fit_ranking_authority": False,
        "profile_fit_top5_authority": False,
        "profile_fit_application_authority": False,
    }


def enrich_profile_fit_coverage(
    row: Mapping[str, object],
    *,
    candidate_preference_tags: Iterable[str] = (),
) -> dict[str, object]:
    enriched = dict(row)
    enriched.update(
        build_profile_fit_coverage(
            row,
            candidate_preference_tags=candidate_preference_tags,
        )
    )
    return enriched


__all__ = [
    "FAILED",
    "INSUFFICIENT_EVIDENCE",
    "PASSED",
    "PROFILE_FIT_COMPLETE",
    "PROFILE_FIT_VERSION",
    "build_profile_fit_coverage",
    "enrich_profile_fit_coverage",
    "parse_candidate_geography_policy",
]
