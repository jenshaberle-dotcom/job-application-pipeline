"""Resolve employer-origin candidates from observed job inventory.

The module is deliberately deterministic and review-only. It does not fetch URLs,
write database state, register connectors, activate sources or change a scheduler.
It consumes already collected observations and returns a finite resolution plus a
bounded reobservation plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

ORIGIN_INVENTORY_RESOLUTION_BOUNDARY = {
    "review_output_only_not_pipeline_input": True,
    "no_provider_call": True,
    "no_network_fetch": True,
    "no_database_read": True,
    "no_database_write": True,
    "no_candidate_status_mutation": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "no_bronze_write": True,
    "no_silver_write": True,
    "no_scheduler_change": True,
    "no_baitjob_assertion": True,
}

SOURCE_ROLES = {
    "official_company",
    "official_ats",
    "group_official",
    "third_party",
    "unknown",
}
ORIGIN_ELIGIBLE_ROLES = {
    "official_company",
    "official_ats",
    "group_official",
}
SOURCE_ROLE_PRIORITY = {
    "official_company": 0,
    "official_ats": 1,
    "group_official": 2,
    "unknown": 3,
    "third_party": 4,
}
REOBSERVATION_DELAYS_DAYS = (1, 3, 7, 14, 30)
DEFAULT_EXTERNAL_SIGNAL_THRESHOLD = 0.75
DEFAULT_JOB_SET_OVERLAP_THRESHOLD = 0.80


def canonical_url_key(url: object) -> str:
    """Return a stable comparison key without inventing URL equivalence."""

    raw = str(url or "").strip()
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return raw.lower()
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.query,
            "",
        )
    )


def _normalized_nonempty(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


@dataclass(frozen=True)
class ExternalJobSignal:
    """State of the job finding that triggered origin discovery."""

    currently_live: bool | None
    confidence: float
    observation_count: int = 1
    origin_miss_count: int = 0

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.observation_count < 0:
            raise ValueError("observation_count must not be negative")
        if self.origin_miss_count < 0:
            raise ValueError("origin_miss_count must not be negative")

    def to_json(self) -> dict[str, object]:
        return {
            "currently_live": self.currently_live,
            "confidence": self.confidence,
            "observation_count": self.observation_count,
            "origin_miss_count": self.origin_miss_count,
        }


@dataclass(frozen=True)
class OriginCandidateInventory:
    """One independently observed seed URL and its relevant job inventory."""

    candidate_id: str
    source_url: str
    source_role: str
    final_url: str | None = None
    canonical_url: str | None = None
    ats_tenant: str | None = None
    employer_scope: str | None = None
    reachable: bool = True
    observed_job_count: int = 0
    relevant_job_count: int = 0
    relevant_job_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id is required")
        if not self.source_url.strip():
            raise ValueError("source_url is required")
        if self.source_role not in SOURCE_ROLES:
            raise ValueError(f"unsupported source_role: {self.source_role}")
        if self.observed_job_count < 0 or self.relevant_job_count < 0:
            raise ValueError("job counts must not be negative")
        if self.relevant_job_count > self.observed_job_count:
            raise ValueError("relevant_job_count must not exceed observed_job_count")
        keys = _normalized_nonempty(self.relevant_job_keys)
        object.__setattr__(self, "relevant_job_keys", keys)

    @property
    def comparison_url(self) -> str:
        return canonical_url_key(self.canonical_url or self.final_url or self.source_url)

    @property
    def has_relevant_jobs(self) -> bool:
        return self.relevant_job_count > 0

    @property
    def origin_eligible(self) -> bool:
        return self.source_role in ORIGIN_ELIGIBLE_ROLES

    def to_json(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "source_url": self.source_url,
            "final_url": self.final_url,
            "canonical_url": self.canonical_url,
            "comparison_url": self.comparison_url,
            "source_role": self.source_role,
            "ats_tenant": self.ats_tenant,
            "employer_scope": self.employer_scope,
            "reachable": self.reachable,
            "observed_job_count": self.observed_job_count,
            "relevant_job_count": self.relevant_job_count,
            "relevant_job_keys": list(self.relevant_job_keys),
            "origin_eligible": self.origin_eligible,
        }


@dataclass(frozen=True)
class OriginSourceFamily:
    """Candidates proven to represent one technical or inventory source family."""

    family_id: str
    candidate_ids: tuple[str, ...]
    canonical_candidate_id: str
    source_roles: tuple[str, ...]
    relevant_job_keys: tuple[str, ...]
    relevant_job_count: int
    origin_eligible: bool
    equivalence_reasons: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "candidate_ids": list(self.candidate_ids),
            "canonical_candidate_id": self.canonical_candidate_id,
            "source_roles": list(self.source_roles),
            "relevant_job_keys": list(self.relevant_job_keys),
            "relevant_job_count": self.relevant_job_count,
            "origin_eligible": self.origin_eligible,
            "equivalence_reasons": list(self.equivalence_reasons),
        }


@dataclass(frozen=True)
class ReobservationPlan:
    mode: str
    next_observation_on: date | None
    next_attempt: int | None
    trigger: str

    def to_json(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "next_observation_on": (
                None if self.next_observation_on is None else self.next_observation_on.isoformat()
            ),
            "next_attempt": self.next_attempt,
            "trigger": self.trigger,
        }


@dataclass(frozen=True)
class OriginInventoryResolution:
    company_key: str
    company_name: str
    status: str
    source_families: tuple[OriginSourceFamily, ...]
    selected_source_family_ids: tuple[str, ...]
    selected_candidate_ids: tuple[str, ...]
    discovery_candidate_ids: tuple[str, ...]
    hypothesis: str | None
    hypothesis_level: str | None
    external_job_signal: ExternalJobSignal
    reobservation: ReobservationPlan
    reasons: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": "origin_inventory_resolution.v1",
            "company_key": self.company_key,
            "company_name": self.company_name,
            "status": self.status,
            "source_families": [family.to_json() for family in self.source_families],
            "selected_source_family_ids": list(self.selected_source_family_ids),
            "selected_candidate_ids": list(self.selected_candidate_ids),
            "discovery_candidate_ids": list(self.discovery_candidate_ids),
            "hypothesis": self.hypothesis,
            "hypothesis_level": self.hypothesis_level,
            "external_job_signal": self.external_job_signal.to_json(),
            "reobservation": self.reobservation.to_json(),
            "reasons": list(self.reasons),
            "boundary": ORIGIN_INVENTORY_RESOLUTION_BOUNDARY,
        }


def _scope_compatible(left: OriginCandidateInventory, right: OriginCandidateInventory) -> bool:
    if not left.employer_scope or not right.employer_scope:
        return True
    return left.employer_scope.strip().lower() == right.employer_scope.strip().lower()


def _job_set_overlap(left: OriginCandidateInventory, right: OriginCandidateInventory) -> float:
    left_jobs = set(left.relevant_job_keys)
    right_jobs = set(right.relevant_job_keys)
    if not left_jobs or not right_jobs:
        return 0.0
    return len(left_jobs & right_jobs) / len(left_jobs | right_jobs)


def candidate_equivalence_reasons(
    left: OriginCandidateInventory,
    right: OriginCandidateInventory,
    *,
    job_set_overlap_threshold: float = DEFAULT_JOB_SET_OVERLAP_THRESHOLD,
) -> tuple[str, ...]:
    """Return only observed reasons that justify one connector/source family."""

    if not _scope_compatible(left, right):
        return ()
    reasons: list[str] = []
    if left.comparison_url == right.comparison_url:
        reasons.append("same_canonical_or_final_url")
    if left.ats_tenant and right.ats_tenant:
        if left.ats_tenant.strip().lower() == right.ats_tenant.strip().lower():
            reasons.append("same_ats_tenant")
    overlap = _job_set_overlap(left, right)
    if overlap >= job_set_overlap_threshold:
        reasons.append(f"relevant_job_set_overlap:{overlap:.3f}")
    return tuple(reasons)


def _canonical_candidate(candidates: Iterable[OriginCandidateInventory]) -> OriginCandidateInventory:
    return min(
        candidates,
        key=lambda item: (
            SOURCE_ROLE_PRIORITY[item.source_role],
            item.comparison_url,
            item.candidate_id,
        ),
    )


def build_source_families(
    candidates: Iterable[OriginCandidateInventory],
    *,
    job_set_overlap_threshold: float = DEFAULT_JOB_SET_OVERLAP_THRESHOLD,
) -> tuple[OriginSourceFamily, ...]:
    """Collapse only candidates with explicit technical or inventory equivalence."""

    items = tuple(candidates)
    if not items:
        return ()
    parent = list(range(len(items)))
    pair_reasons: dict[tuple[int, int], tuple[str, ...]] = {}

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left_index: int, right_index: int) -> None:
        left_root = find(left_index)
        right_root = find(right_index)
        if left_root != right_root:
            parent[right_root] = left_root

    for left_index, left in enumerate(items):
        for right_index in range(left_index + 1, len(items)):
            right = items[right_index]
            reasons = candidate_equivalence_reasons(
                left,
                right,
                job_set_overlap_threshold=job_set_overlap_threshold,
            )
            if reasons:
                pair_reasons[(left_index, right_index)] = reasons
                union(left_index, right_index)

    grouped: dict[int, list[int]] = {}
    for index in range(len(items)):
        grouped.setdefault(find(index), []).append(index)

    families: list[OriginSourceFamily] = []
    for indexes in grouped.values():
        family_candidates = [items[index] for index in indexes]
        canonical = _canonical_candidate(family_candidates)
        candidate_ids = tuple(sorted(item.candidate_id for item in family_candidates))
        reasons = sorted(
            {
                reason
                for (left_index, right_index), values in pair_reasons.items()
                if left_index in indexes and right_index in indexes
                for reason in values
            }
        )
        job_keys = _normalized_nonempty(
            key for item in family_candidates for key in item.relevant_job_keys
        )
        families.append(
            OriginSourceFamily(
                family_id="source-family:" + "+".join(candidate_ids),
                candidate_ids=candidate_ids,
                canonical_candidate_id=canonical.candidate_id,
                source_roles=tuple(sorted({item.source_role for item in family_candidates})),
                relevant_job_keys=job_keys,
                relevant_job_count=max(
                    len(job_keys),
                    max(item.relevant_job_count for item in family_candidates),
                ),
                origin_eligible=any(item.origin_eligible for item in family_candidates),
                equivalence_reasons=tuple(reasons),
            )
        )
    return tuple(sorted(families, key=lambda family: family.family_id))


def plan_reobservation(
    *,
    as_of: date,
    failed_attempt: int,
    new_external_job_event: bool = False,
) -> ReobservationPlan:
    """Return a degressive schedule that becomes event-only after five retries."""

    if failed_attempt < 0:
        raise ValueError("failed_attempt must not be negative")
    if new_external_job_event:
        return ReobservationPlan(
            mode="immediate_event",
            next_observation_on=as_of,
            next_attempt=0,
            trigger="new_external_job_finding",
        )
    if failed_attempt < len(REOBSERVATION_DELAYS_DAYS):
        delay = REOBSERVATION_DELAYS_DAYS[failed_attempt]
        return ReobservationPlan(
            mode="scheduled",
            next_observation_on=as_of + timedelta(days=delay),
            next_attempt=failed_attempt + 1,
            trigger=f"degressive_retry_after_{delay}_days",
        )
    return ReobservationPlan(
        mode="event_only",
        next_observation_on=None,
        next_attempt=None,
        trigger="new_external_job_finding_or_operator_reactivation",
    )


def _hypothesis_level(signal: ExternalJobSignal) -> str:
    if signal.observation_count >= 3 and signal.origin_miss_count >= 3:
        return "strong_but_reversible"
    if signal.observation_count >= 2 and signal.origin_miss_count >= 2:
        return "probable"
    return "possible"


def resolve_origin_inventory(
    *,
    company_key: str,
    company_name: str,
    candidates: Iterable[OriginCandidateInventory],
    external_job_signal: ExternalJobSignal,
    as_of: date,
    failed_reobservation_attempt: int = 0,
    new_external_job_event: bool = False,
    external_signal_threshold: float = DEFAULT_EXTERNAL_SIGNAL_THRESHOLD,
    job_set_overlap_threshold: float = DEFAULT_JOB_SET_OVERLAP_THRESHOLD,
) -> OriginInventoryResolution:
    """Resolve one employer without converting observations into mutation truth."""

    if not company_key.strip() or not company_name.strip():
        raise ValueError("company_key and company_name are required")
    if not 0.0 <= external_signal_threshold <= 1.0:
        raise ValueError("external_signal_threshold must be between 0 and 1")
    if not 0.0 <= job_set_overlap_threshold <= 1.0:
        raise ValueError("job_set_overlap_threshold must be between 0 and 1")

    candidate_items = tuple(candidates)
    families = build_source_families(
        candidate_items,
        job_set_overlap_threshold=job_set_overlap_threshold,
    )
    origin_job_families = tuple(
        family
        for family in families
        if family.origin_eligible and family.relevant_job_count > 0
    )
    third_party_job_candidates = tuple(
        sorted(
            item.candidate_id
            for item in candidate_items
            if item.source_role == "third_party" and item.has_relevant_jobs
        )
    )

    selected_family_ids: tuple[str, ...] = ()
    selected_candidate_ids: tuple[str, ...] = ()
    hypothesis: str | None = None
    hypothesis_level: str | None = None
    reasons: list[str] = []

    if len(origin_job_families) == 1:
        family = origin_job_families[0]
        selected_family_ids = (family.family_id,)
        selected_candidate_ids = (family.canonical_candidate_id,)
        if len(family.candidate_ids) == 1:
            status = "confirmed_origin"
            reasons.append("exactly one origin-eligible source family contains relevant jobs")
        else:
            status = "equivalent_source_family"
            reasons.append(
                "multiple seed URLs contain relevant jobs but represent one proven source family"
            )
        reobservation = ReobservationPlan(
            mode="not_required",
            next_observation_on=None,
            next_attempt=None,
            trigger="resolved_origin_inventory",
        )
    elif len(origin_job_families) > 1:
        status = "multi_origin_coverage"
        selected_family_ids = tuple(family.family_id for family in origin_job_families)
        selected_candidate_ids = tuple(
            family.canonical_candidate_id for family in origin_job_families
        )
        reasons.append(
            "multiple non-equivalent origin-eligible source families contain relevant jobs"
        )
        reobservation = ReobservationPlan(
            mode="not_required",
            next_observation_on=None,
            next_attempt=None,
            trigger="resolved_multi_origin_inventory",
        )
    else:
        reobservation = plan_reobservation(
            as_of=as_of,
            failed_attempt=failed_reobservation_attempt,
            new_external_job_event=new_external_job_event,
        )
        external_signal_is_strong = (
            external_job_signal.currently_live is True
            and external_job_signal.confidence >= external_signal_threshold
        )
        if third_party_job_candidates:
            status = "third_party_discovery_only"
            reasons.append(
                "relevant jobs were observed only on third-party sources; no origin source was selected"
            )
            if external_signal_is_strong:
                hypothesis = "employer_may_publish_through_third_party_only"
                hypothesis_level = _hypothesis_level(external_job_signal)
                reasons.append(
                    "external live-job evidence supports a reversible third-party-only hypothesis"
                )
        elif external_signal_is_strong:
            status = "official_origin_unproven"
            hypothesis = "official_origin_not_observed_for_current_live_job"
            hypothesis_level = _hypothesis_level(external_job_signal)
            reasons.append(
                "a high-confidence external job remains live but no candidate exposes relevant inventory"
            )
        elif external_job_signal.currently_live is False:
            status = "dormant_origin_candidate"
            reasons.append(
                "the triggering job is no longer live and no candidate exposes relevant inventory"
            )
        else:
            status = "insufficient_evidence"
            reasons.append(
                "neither current external-job state nor origin inventory is strong enough for a hypothesis"
            )

    return OriginInventoryResolution(
        company_key=company_key,
        company_name=company_name,
        status=status,
        source_families=families,
        selected_source_family_ids=selected_family_ids,
        selected_candidate_ids=selected_candidate_ids,
        discovery_candidate_ids=third_party_job_candidates,
        hypothesis=hypothesis,
        hypothesis_level=hypothesis_level,
        external_job_signal=external_job_signal,
        reobservation=reobservation,
        reasons=tuple(reasons),
    )


def candidate_from_mapping(payload: Mapping[str, object]) -> OriginCandidateInventory:
    return OriginCandidateInventory(
        candidate_id=str(payload["candidate_id"]),
        source_url=str(payload["source_url"]),
        source_role=str(payload["source_role"]),
        final_url=None if payload.get("final_url") is None else str(payload["final_url"]),
        canonical_url=(
            None if payload.get("canonical_url") is None else str(payload["canonical_url"])
        ),
        ats_tenant=None if payload.get("ats_tenant") is None else str(payload["ats_tenant"]),
        employer_scope=(
            None if payload.get("employer_scope") is None else str(payload["employer_scope"])
        ),
        reachable=bool(payload.get("reachable", True)),
        observed_job_count=int(payload.get("observed_job_count", 0)),
        relevant_job_count=int(payload.get("relevant_job_count", 0)),
        relevant_job_keys=tuple(payload.get("relevant_job_keys") or ()),
    )
