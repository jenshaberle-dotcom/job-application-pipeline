"""Generic Product V1 discovery-candidate to origin-URL bridge contracts.

The bridge interprets persisted discovery provenance and selects candidates for the
existing origin-discovery and CAND-001 URL-persistence runtime.  Company identity
is evidence only and never controls the transition rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping, Sequence

from src.search_intelligence.origin_seed_pool import normalize_company_key

APPROVAL_TOKEN = "approve_product_e2e_origin_url_persistence"
SUPPORTED_DISCOVERY_SOURCE_CLASSES = (
    "aggregator_company_discovery",
    "public_job_api_discovery",
)
_SOURCE_CLASS_PATTERN = re.compile(
    r"(?:^|;\s*)discovery_source_class=([^;]+)", re.IGNORECASE
)


@dataclass(frozen=True)
class OriginUrlBridgeCandidate:
    candidate_id: int
    company_key: str
    company_name: str
    status: str
    candidate_url: str | None
    notes: str | None
    discovery_source_class: str | None


@dataclass(frozen=True)
class OriginUrlBridgePlan:
    candidate_id: int
    company_key: str
    company_name: str
    discovery_source_class: str | None
    candidate_status: str
    current_candidate_url: str | None
    action: str
    plan_status: str
    origin_discovery_allowed: bool
    apply_target_allowed: bool
    reason: str


def discovery_source_class_from_notes(notes: str | None) -> str | None:
    """Read the explicit ingress provenance marker without inferring from company data."""

    match = _SOURCE_CLASS_PATTERN.search(str(notes or ""))
    if match is None:
        return None
    value = match.group(1).strip().lower()
    return value or None


def candidate_from_row(row: Mapping[str, object]) -> OriginUrlBridgeCandidate:
    notes = str(row.get("notes") or "") or None
    return OriginUrlBridgeCandidate(
        candidate_id=int(row["id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        status=str(row["status"]),
        candidate_url=str(row.get("candidate_url") or "").strip() or None,
        notes=notes,
        discovery_source_class=discovery_source_class_from_notes(notes),
    )


def build_origin_url_bridge_plan(
    candidate: OriginUrlBridgeCandidate,
) -> OriginUrlBridgePlan:
    source_class = candidate.discovery_source_class
    company_key = normalize_company_key(candidate.company_key)
    common = {
        "candidate_id": candidate.candidate_id,
        "company_key": company_key,
        "company_name": candidate.company_name,
        "discovery_source_class": source_class,
        "candidate_status": candidate.status,
        "current_candidate_url": candidate.candidate_url,
    }

    if not company_key or not candidate.company_name.strip():
        return OriginUrlBridgePlan(
            **common,
            action="block_missing_employer_identity",
            plan_status="capability_gap",
            origin_discovery_allowed=False,
            apply_target_allowed=False,
            reason="Origin discovery requires an explicit canonical employer identity.",
        )
    if candidate.candidate_url:
        return OriginUrlBridgePlan(
            **common,
            action="no_action_origin_url_already_persisted",
            plan_status="passed",
            origin_discovery_allowed=False,
            apply_target_allowed=True,
            reason="The candidate already stores an origin URL; replay is idempotent.",
        )
    if source_class is None:
        return OriginUrlBridgePlan(
            **common,
            action="block_missing_discovery_provenance",
            plan_status="capability_gap",
            origin_discovery_allowed=False,
            apply_target_allowed=False,
            reason=(
                "The candidate has no explicit discovery_source_class provenance marker; "
                "the bridge must not infer one from company identity."
            ),
        )
    if source_class not in SUPPORTED_DISCOVERY_SOURCE_CLASSES:
        return OriginUrlBridgePlan(
            **common,
            action="valid_stop_source_class_outside_bridge",
            plan_status="valid_stop",
            origin_discovery_allowed=False,
            apply_target_allowed=False,
            reason=(
                "This bridge is limited to aggregator and public-job-API discovery "
                "candidates; other provenance classes keep their existing lifecycle."
            ),
        )
    if candidate.status != "discovery":
        return OriginUrlBridgePlan(
            **common,
            action="valid_stop_candidate_not_in_discovery_state",
            plan_status="valid_stop",
            origin_discovery_allowed=False,
            apply_target_allowed=False,
            reason=(
                "Only unresolved discovery-state candidates may enter the generic "
                "origin URL bridge."
            ),
        )
    return OriginUrlBridgePlan(
        **common,
        action="run_bounded_origin_discovery_then_cand001",
        plan_status="ready_for_origin_discovery",
        origin_discovery_allowed=True,
        apply_target_allowed=True,
        reason=(
            "The source-neutral discovery candidate is ready for bounded origin "
            "validation and the existing CAND-001 persistence gate."
        ),
    )


def select_source_diverse_plans(
    plans: Iterable[OriginUrlBridgePlan],
    *,
    limit: int,
    preferred_source_classes: Sequence[str] = SUPPORTED_DISCOVERY_SOURCE_CLASSES,
) -> tuple[OriginUrlBridgePlan, ...]:
    if limit < 1 or limit > 5:
        raise ValueError("limit must be between 1 and 5")
    eligible = sorted(
        (plan for plan in plans if plan.origin_discovery_allowed),
        key=lambda item: (item.candidate_id, item.company_key),
    )
    selected: list[OriginUrlBridgePlan] = []
    selected_ids: set[int] = set()
    for source_class in preferred_source_classes:
        match = next(
            (
                plan
                for plan in eligible
                if plan.discovery_source_class == source_class
                and plan.candidate_id not in selected_ids
            ),
            None,
        )
        if match is not None:
            selected.append(match)
            selected_ids.add(match.candidate_id)
        if len(selected) == limit:
            return tuple(selected)
    for plan in eligible:
        if plan.candidate_id in selected_ids:
            continue
        selected.append(plan)
        selected_ids.add(plan.candidate_id)
        if len(selected) == limit:
            break
    return tuple(selected)


def parse_exact_target(value: str) -> tuple[int, str]:
    raw_id, separator, raw_key = value.partition(":")
    if not separator or not raw_id.isdigit():
        raise ValueError("Targets must use the exact format candidate_id:company_key.")
    company_key = normalize_company_key(raw_key)
    if not company_key:
        raise ValueError("Targets must include a non-empty canonical company_key.")
    return int(raw_id), company_key


def select_exact_target_plans(
    plans: Iterable[OriginUrlBridgePlan],
    *,
    requested_targets: Iterable[str],
) -> tuple[OriginUrlBridgePlan, ...]:
    by_id = {plan.candidate_id: plan for plan in plans}
    selected: list[OriginUrlBridgePlan] = []
    selected_ids: set[int] = set()
    for raw_target in requested_targets:
        candidate_id, company_key = parse_exact_target(raw_target)
        if candidate_id in selected_ids:
            raise ValueError(f"Duplicate candidate target: {candidate_id}.")
        plan = by_id.get(candidate_id)
        if plan is None:
            raise ValueError(
                f"Candidate target {candidate_id}:{company_key} is not present in current DB state."
            )
        if plan.company_key != company_key:
            raise ValueError(
                f"Candidate target {candidate_id} has company_key={plan.company_key!r}, "
                f"not {company_key!r}."
            )
        if not plan.apply_target_allowed:
            raise ValueError(
                f"Candidate target {candidate_id}:{company_key} is blocked: {plan.action}."
            )
        selected.append(plan)
        selected_ids.add(candidate_id)
    return tuple(selected)
