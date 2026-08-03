"""Generic discovery-to-candidate ingress planning.

Discovery provenance may affect evidence requirements, but it must never create a
company-specific downstream path.  This module contains deterministic planning
logic only; database mutation is owned by the explicit CLI apply boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.search_intelligence.origin_seed_pool import normalize_company_key
from src.search_intelligence.product_e2e_golden_path import DiscoveryCase

APPROVAL_TOKEN = "approve_product_e2e_discovery_candidate_creation"
SUPPORTED_INGRESS_CLASSES = {
    "aggregator_company_discovery",
    "public_job_api_discovery",
    "manual_observation",
}


@dataclass(frozen=True)
class ExistingCandidate:
    candidate_id: int
    company_key: str
    company_name: str
    status: str


@dataclass(frozen=True)
class CandidateIngressPlan:
    case_id: str
    discovery_source_class: str
    seed_type: str
    seed_source_table: str
    company_key: str | None
    company_name: str | None
    source_name: str | None
    seed_url: str | None
    action: str
    plan_status: str
    create_allowed_after_explicit_approval: bool
    manual_observation_opt_in_required: bool
    reason: str
    existing_candidate_id: int | None = None
    source_name_candidate: str | None = None
    source_family_candidate: str | None = None
    source_type_candidate: str | None = None
    risk_level: str | None = None


def canonical_company_key(case: DiscoveryCase) -> str | None:
    key = normalize_company_key(case.company_key or case.company_name)
    return key or None


def _candidate_fields(company_key: str) -> tuple[str, str, str]:
    return (
        f"{company_key}:discovery",
        company_key,
        "employer_origin_career_site",
    )


def build_candidate_ingress_plan(
    case: DiscoveryCase,
    existing_candidate: ExistingCandidate | None,
) -> CandidateIngressPlan:
    """Plan one source-neutral discovery-to-candidate transition."""

    company_key = canonical_company_key(case)
    if existing_candidate is not None:
        return CandidateIngressPlan(
            case_id=case.case_id,
            discovery_source_class=case.discovery_source_class,
            seed_type=case.seed_type,
            seed_source_table=case.seed_source_table,
            company_key=company_key,
            company_name=case.company_name,
            source_name=case.source_name,
            seed_url=case.seed_url,
            action="skip_existing_candidate",
            plan_status="passed",
            create_allowed_after_explicit_approval=False,
            manual_observation_opt_in_required=False,
            reason="A reusable employer-origin candidate already exists.",
            existing_candidate_id=existing_candidate.candidate_id,
        )

    if not company_key or not case.company_name:
        return CandidateIngressPlan(
            case_id=case.case_id,
            discovery_source_class=case.discovery_source_class,
            seed_type=case.seed_type,
            seed_source_table=case.seed_source_table,
            company_key=company_key,
            company_name=case.company_name,
            source_name=case.source_name,
            seed_url=case.seed_url,
            action="block_missing_employer_identity",
            plan_status="capability_gap",
            create_allowed_after_explicit_approval=False,
            manual_observation_opt_in_required=False,
            reason="Candidate creation requires a normalized key and explicit employer name.",
        )

    if case.discovery_source_class not in SUPPORTED_INGRESS_CLASSES:
        return CandidateIngressPlan(
            case_id=case.case_id,
            discovery_source_class=case.discovery_source_class,
            seed_type=case.seed_type,
            seed_source_table=case.seed_source_table,
            company_key=company_key,
            company_name=case.company_name,
            source_name=case.source_name,
            seed_url=case.seed_url,
            action="not_primary_discovery_ingress",
            plan_status="valid_stop",
            create_allowed_after_explicit_approval=False,
            manual_observation_opt_in_required=False,
            reason=(
                "This path only normalizes aggregator, public-job-API and manual "
                "discovery signals. Existing origin evidence follows the origin lifecycle."
            ),
        )

    source_name_candidate, source_family_candidate, source_type_candidate = (
        _candidate_fields(company_key)
    )
    if case.discovery_source_class == "manual_observation":
        return CandidateIngressPlan(
            case_id=case.case_id,
            discovery_source_class=case.discovery_source_class,
            seed_type=case.seed_type,
            seed_source_table=case.seed_source_table,
            company_key=company_key,
            company_name=case.company_name,
            source_name=case.source_name,
            seed_url=case.seed_url,
            action="create_discovery_candidate_after_manual_opt_in",
            plan_status="operator_decision_required",
            create_allowed_after_explicit_approval=True,
            manual_observation_opt_in_required=True,
            reason=(
                "A manual observation identifies an employer, but explicit operator "
                "opt-in is required before it becomes candidate state."
            ),
            source_name_candidate=source_name_candidate,
            source_family_candidate=source_family_candidate,
            source_type_candidate=source_type_candidate,
            risk_level="medium",
        )

    reason = (
        "A concrete public job API signal identifies an employer; create only a "
        "discovery candidate and leave origin URL unresolved."
        if case.discovery_source_class == "public_job_api_discovery"
        else (
            "A bounded aggregator company signal identifies an employer; create only "
            "a discovery candidate and leave origin URL unresolved."
        )
    )
    return CandidateIngressPlan(
        case_id=case.case_id,
        discovery_source_class=case.discovery_source_class,
        seed_type=case.seed_type,
        seed_source_table=case.seed_source_table,
        company_key=company_key,
        company_name=case.company_name,
        source_name=case.source_name,
        seed_url=case.seed_url,
        action="create_discovery_candidate",
        plan_status="ready_for_explicit_apply",
        create_allowed_after_explicit_approval=True,
        manual_observation_opt_in_required=False,
        reason=reason,
        source_name_candidate=source_name_candidate,
        source_family_candidate=source_family_candidate,
        source_type_candidate=source_type_candidate,
        risk_level="unknown",
    )


def select_apply_plans(
    plans: Iterable[CandidateIngressPlan],
    *,
    requested_company_keys: Iterable[str],
    include_manual_observations: bool,
) -> tuple[CandidateIngressPlan, ...]:
    """Select an exact bounded apply set and fail closed on ambiguity."""

    requested = tuple(
        dict.fromkeys(
            key
            for raw in requested_company_keys
            if (key := normalize_company_key(raw))
        )
    )
    by_key: dict[str, CandidateIngressPlan] = {}
    for plan in plans:
        if plan.company_key:
            by_key.setdefault(plan.company_key, plan)

    selected: list[CandidateIngressPlan] = []
    for company_key in requested:
        plan = by_key.get(company_key)
        if plan is None:
            raise ValueError(
                f"Requested company_key {company_key!r} is not present in the current plan."
            )
        if not plan.create_allowed_after_explicit_approval:
            raise ValueError(
                f"Candidate creation is not allowed for {company_key!r}: {plan.action}."
            )
        if plan.manual_observation_opt_in_required and not include_manual_observations:
            raise ValueError(
                f"Manual observation {company_key!r} requires explicit manual opt-in."
            )
        selected.append(plan)
    return tuple(selected)
