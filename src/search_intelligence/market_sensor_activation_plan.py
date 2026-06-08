from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

BA_SOURCE_NAME = "bundesagentur_fuer_arbeit"
BA_REMOTE_NATIONWIDE_PROFILE_NAME = "ba_data_engineering_remote_nationwide_review"


@dataclass(frozen=True)
class MarketSensorProfile:
    id: int
    profile_name: str
    source_name: str
    search_term: str | None
    search_location: str | None
    search_radius_km: int | None
    offer_type: int | None
    page_size: int
    is_active: bool

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "MarketSensorProfile":
        return cls(
            id=int(row["id"]),
            profile_name=str(row["profile_name"]),
            source_name=str(row["source_name"]),
            search_term=_optional_text(row.get("search_term")),
            search_location=_optional_text(row.get("search_location")),
            search_radius_km=_optional_int(row.get("search_radius_km")),
            offer_type=_optional_int(row.get("offer_type")),
            page_size=int(row["page_size"]),
            is_active=bool(row["is_active"]),
        )


@dataclass(frozen=True)
class MarketSensorSearchTerm:
    id: int | None
    search_profile_id: int
    search_term: str
    is_active: bool

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "MarketSensorSearchTerm":
        return cls(
            id=_optional_int(row.get("id")),
            search_profile_id=int(row["search_profile_id"]),
            search_term=str(row["search_term"]),
            is_active=bool(row["is_active"]),
        )


@dataclass(frozen=True)
class ProposedSearchProfile:
    profile_name: str
    source_name: str
    search_term: str
    search_location: str | None
    search_radius_km: int | None
    offer_type: int | None
    page_size: int
    is_active: bool
    coverage_mode: str
    remote_option_strategy: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketSensorActivationPlan:
    work_item: str
    source_name: str
    overall_status: str
    generated_at_utc: str
    generic_requirement: str
    current_profiles: tuple[MarketSensorProfile, ...]
    current_search_terms: tuple[MarketSensorSearchTerm, ...]
    proposed_profile: ProposedSearchProfile | None
    proposed_search_terms: tuple[str, ...]
    activation_changes: Mapping[str, Any]
    activation_gates: tuple[str, ...]
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "sensor001b.ba_remote_nationwide_activation_plan.v1",
            "generated_at_utc": self.generated_at_utc,
            "work_item": self.work_item,
            "source_name": self.source_name,
            "overall_status": self.overall_status,
            "generic_requirement": self.generic_requirement,
            "safety_boundary": {
                "read_only": True,
                "external_requests": False,
                "database_writes": False,
                "pipeline_mutation": False,
                "candidate_or_gate_mutation": False,
                "connector_activation": False,
                "scheduler_mutation": False,
            },
            "current_profiles": [asdict(profile) for profile in self.current_profiles],
            "current_search_terms": [asdict(term) for term in self.current_search_terms],
            "proposed_profile": self.proposed_profile.as_dict() if self.proposed_profile else None,
            "proposed_search_terms": list(self.proposed_search_terms),
            "activation_changes": dict(self.activation_changes),
            "activation_gates": list(self.activation_gates),
            "notes": list(self.notes),
        }


def build_ba_remote_nationwide_activation_plan(
    profiles: Iterable[MarketSensorProfile],
    search_terms: Iterable[MarketSensorSearchTerm],
) -> MarketSensorActivationPlan:
    profile_tuple = tuple(profile for profile in profiles if profile.source_name == BA_SOURCE_NAME)
    term_tuple = tuple(search_terms)

    now = datetime.now(timezone.utc).isoformat()
    generic_requirement = (
        "Every market sensor must make local/regional coverage and Germany-wide "
        "remote-option coverage explicit. BA is the first concrete activation-plan case."
    )

    if not profile_tuple:
        return MarketSensorActivationPlan(
            work_item="SENSOR-001B BA Remote/Nationwide Activation Plan",
            source_name=BA_SOURCE_NAME,
            overall_status="baseline_missing",
            generated_at_utc=now,
            generic_requirement=generic_requirement,
            current_profiles=(),
            current_search_terms=(),
            proposed_profile=None,
            proposed_search_terms=(),
            activation_changes={
                "activate_now": False,
                "create_profile_now": False,
                "reason": "No existing BA baseline profile was found.",
            },
            activation_gates=(
                "Create or inspect a local/regional baseline before planning remote/nationwide expansion.",
            ),
            notes=(
                "The project must not create a productive remote/nationwide profile without a known BA baseline.",
            ),
        )

    baseline = select_baseline_profile(profile_tuple)
    proposed_terms = collect_proposed_terms(baseline, term_tuple)
    proposed_profile = ProposedSearchProfile(
        profile_name=BA_REMOTE_NATIONWIDE_PROFILE_NAME,
        source_name=BA_SOURCE_NAME,
        search_term=proposed_terms[0],
        search_location=None,
        search_radius_km=None,
        offer_type=baseline.offer_type,
        page_size=min(max(baseline.page_size, 1), 10),
        is_active=False,
        coverage_mode="germany_wide_remote_option_review",
        remote_option_strategy=(
            "BA has no confirmed server-side remote filter in the current project contract; "
            "plan a Germany-wide bounded search first, then validate remote/hybrid signals downstream."
        ),
    )

    return MarketSensorActivationPlan(
        work_item="SENSOR-001B BA Remote/Nationwide Activation Plan",
        source_name=BA_SOURCE_NAME,
        overall_status="review_required",
        generated_at_utc=now,
        generic_requirement=generic_requirement,
        current_profiles=profile_tuple,
        current_search_terms=tuple(term for term in term_tuple if term.search_profile_id == baseline.id),
        proposed_profile=proposed_profile,
        proposed_search_terms=proposed_terms,
        activation_changes={
            "activate_now": False,
            "create_profile_now": False,
            "proposed_profile_is_active": False,
            "scheduler_changes_now": False,
            "pipeline_mutation_now": False,
            "next_work_item": "SENSOR-001C BA Remote/Nationwide Controlled Activation",
            "reason": (
                "SENSOR-001B only produces a reviewable activation plan. "
                "The proposed profile remains inactive until a later gated activation step."
            ),
        },
        activation_gates=(
            "Review the inactive proposed profile and search terms.",
            "Confirm that leaving search_location/search_radius_km empty is the intended BA nationwide-query strategy.",
            "Run a bounded sample ingestion only after explicit approval.",
            "Measure new inserts, duplicate rate, profile relevance, location distribution, and remote/hybrid signal quality.",
            "Keep the existing Hannover/50km profile active and unchanged.",
            "Promote to active only in a separate reviewed migration or operator action.",
        ),
        notes=(
            "The existing BA profile is local/regional and should not be repurposed.",
            "Remote-option discovery is generic market-sensor behavior, not a BA-only special case.",
            "Because BA remote filtering is not confirmed as server-side capability, the plan treats remote as a downstream evidence signal.",
        ),
    )


def select_baseline_profile(profiles: tuple[MarketSensorProfile, ...]) -> MarketSensorProfile:
    active_profiles = tuple(profile for profile in profiles if profile.is_active)
    candidates = active_profiles or profiles
    local_candidates = tuple(
        profile
        for profile in candidates
        if profile.search_location and profile.search_radius_km is not None
    )
    return (local_candidates or candidates)[0]


def collect_proposed_terms(
    baseline: MarketSensorProfile,
    terms: Iterable[MarketSensorSearchTerm],
) -> tuple[str, ...]:
    active_terms = [
        term.search_term
        for term in terms
        if term.search_profile_id == baseline.id and term.is_active
    ]
    if baseline.search_term:
        active_terms.insert(0, baseline.search_term)
    return dedupe_terms(active_terms) or ("Data Engineer",)


def dedupe_terms(terms: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for term in terms:
        cleaned = " ".join(str(term).split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            deduped.append(cleaned)
    return tuple(deduped)


def render_activation_sql_draft(plan: MarketSensorActivationPlan) -> str:
    if plan.proposed_profile is None:
        return (
            "-- SENSOR-001B BA Remote/Nationwide Activation Plan\n"
            "-- No SQL draft generated because no proposed profile exists.\n"
        )

    profile = plan.proposed_profile
    terms_sql = ",\n        ".join(f"({_sql_literal(term)})" for term in plan.proposed_search_terms)

    return f"""-- SENSOR-001B BA Remote/Nationwide Activation Plan
-- REVIEW DRAFT ONLY.
-- This draft intentionally ends with ROLLBACK and keeps the proposed profile inactive.
-- Do not use this as a productive migration without a separate SENSOR-001C approval step.

BEGIN;

WITH profile_insert AS (
    INSERT INTO search_profiles (
        profile_name,
        source_name,
        search_term,
        search_location,
        search_radius_km,
        offer_type,
        page_size,
        is_active
    )
    SELECT
        {_sql_literal(profile.profile_name)},
        {_sql_literal(profile.source_name)},
        {_sql_literal(profile.search_term)},
        NULL,
        NULL,
        {profile.offer_type if profile.offer_type is not None else "NULL"},
        {profile.page_size},
        FALSE
    WHERE NOT EXISTS (
        SELECT 1
        FROM search_profiles
        WHERE profile_name = {_sql_literal(profile.profile_name)}
    )
    RETURNING id
),
profile_ref AS (
    SELECT id FROM profile_insert
    UNION ALL
    SELECT id
    FROM search_profiles
    WHERE profile_name = {_sql_literal(profile.profile_name)}
    LIMIT 1
),
terms(search_term) AS (
    VALUES
        {terms_sql}
)
INSERT INTO search_terms (
    search_profile_id,
    search_term,
    is_active
)
SELECT
    profile_ref.id,
    terms.search_term,
    TRUE
FROM profile_ref
CROSS JOIN terms
WHERE NOT EXISTS (
    SELECT 1
    FROM search_terms existing
    WHERE existing.search_profile_id = profile_ref.id
      AND lower(existing.search_term) = lower(terms.search_term)
);

ROLLBACK;
"""


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
