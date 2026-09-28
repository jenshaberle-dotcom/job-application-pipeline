"""Read-only job-first Employer Discovery Census for JAP Classic.

Every employer admitted to the census must be backed by at least one current job
observation that passes JAP-owned role/skill relevance. Census accessibility is\nrecall-oriented and intentionally separate from Silver accessibility. Sensor jobs have
discovery evidence authority only; this module performs no external requests and
no database, Bronze, Silver, Product, ranking, Fit, application, or connector writes.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable

from src.normalization.company_keys import normalize_company_key
from src.search_intelligence.market_sensor_catalog import CORE_SENSORS
from src.silver.relevance import (
    get_role_matches,
    get_skill_matches,
)

CENSUS_SCHEMA = "job_application_pipeline.employer_discovery_census.v1"
RESIDUAL_SENSORS = ("jooble", "adzuna", "linkedin", "indeed")


@dataclass(frozen=True)
class MarketJobObservation:
    source: str
    title: str
    company_name: str | None
    location: str | None
    observed_at_utc: str
    reference: str
    search_term: str | None = None
    location_signal: str | None = None
    description: str = ""
    remote_signal: bool = False

    @property
    def job_hash(self) -> str:
        return hashlib.sha256(
            f"{self.source}\n{self.reference}".encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class QualifiedJob:
    observation: MarketJobObservation
    company_key: str
    matching_roles: tuple[str, ...]
    local_match: bool
    remote_de_match: bool
    location_confidence: str
    location_reason: str


def _as_silver_job(observation: MarketJobObservation) -> dict:
    return {
        "source_name": observation.source,
        "raw_data": {
            "job": {
                "title": observation.title,
                "description": observation.description,
                "company_name": observation.company_name,
                "location": observation.location,
            }
        },
    }


def qualify_observation(observation: MarketJobObservation) -> QualifiedJob | None:
    """Fail closed unless job relevance and explicit employer attribution both hold."""
    company_name = " ".join(str(observation.company_name or "").split()).strip()
    if not company_name:
        return None

    raw_job = _as_silver_job(observation)
    roles = tuple(sorted(set(get_role_matches(raw_job))))
    skills = tuple(sorted(set(get_skill_matches(raw_job))))
    # Reuse canonical Silver role/skill semantics, but not Silver accessibility:
    # Census discovery intentionally owns a more recall-oriented location policy.
    if not roles and len(skills) < 2:
        return None
    location = str(observation.location or "").casefold()
    local = "hannover" in location or "hanover" in location
    remote_de = observation.remote_signal and any(
        token in location for token in ("deutschland", "germany")
    )

    # Discovery/Bronze is recall-oriented. Reject only when location evidence is
    # strong enough to establish an out-of-profile onsite job. Ambiguous or missing
    # location evidence survives for downstream employer-origin qualification.
    known_outside_target = any(
        token in location
        for token in (
            "berlin", "hamburg", "munich", "münchen", "cologne", "köln",
            "frankfurt", "dublin", "ireland", "london", "united kingdom",
        )
    )
    remote_hint = observation.remote_signal or "remote" in location
    if known_outside_target and not remote_hint:
        return None

    if local:
        location_confidence = "high"
        location_reason = "hannover_local"
    elif remote_de:
        location_confidence = "high"
        location_reason = "explicit_germany_remote"
    elif remote_hint:
        location_confidence = "uncertain"
        location_reason = "remote_hint_needs_origin_qualification"
    else:
        location_confidence = "uncertain"
        location_reason = "location_unknown_needs_origin_qualification"

    return QualifiedJob(
        observation=observation,
        company_key=normalize_company_key(company_name),
        matching_roles=roles,
        local_match=local,
        remote_de_match=remote_de,
        location_confidence=location_confidence,
        location_reason=location_reason,
    )


def build_employer_discovery_census(
    observations: Iterable[MarketJobObservation],
    *,
    known_company_keys: Iterable[str] = (),
) -> dict[str, object]:
    """Build a deterministic read-only census from job-qualified employer evidence."""
    observed = tuple(observations)
    known = {normalize_company_key(value) for value in known_company_keys if value}
    qualified = tuple(
        job for item in observed if (job := qualify_observation(item)) is not None
    )

    grouped: dict[str, list[QualifiedJob]] = {}
    for job in qualified:
        grouped.setdefault(job.company_key, []).append(job)

    employers: list[dict[str, object]] = []
    for company_key in sorted(grouped):
        jobs = grouped[company_key]
        # Invariant is structural: a row cannot exist without >=1 qualifying job.
        assert jobs
        newest = max(job.observation.observed_at_utc for job in jobs)
        employers.append(
            {
                "company_key": company_key,
                "company_name": jobs[0].observation.company_name,
                "matching_job_count": len({job.observation.job_hash for job in jobs}),
                "matching_roles": sorted({role for job in jobs for role in job.matching_roles}),
                "local_matches": sum(job.local_match for job in jobs),
                "remote_de_matches": sum(job.remote_de_match for job in jobs),
                "location_confidence": (
                    "high" if all(job.location_confidence == "high" for job in jobs)
                    else "uncertain"
                ),
                "location_reasons": sorted({job.location_reason for job in jobs}),
                "newest_seen": newest,
                "evidence_sources": sorted({job.observation.source for job in jobs}),
                "sample_job_hashes": sorted({job.observation.job_hash for job in jobs})[:3],
                "origin_status": "known_candidate" if company_key in known else "novel",
            }
        )

    by_source: dict[str, dict[str, object]] = {}
    sources = sorted({item.source for item in observed})
    for source in sources:
        source_observed = [item for item in observed if item.source == source]
        source_qualified = [job for job in qualified if job.observation.source == source]
        attributed = [item for item in source_observed if str(item.company_name or "").strip()]
        unique_employers = {job.company_key for job in source_qualified}
        by_source[source] = {
            "observed_jobs": len(source_observed),
            "qualifying_jobs": len({job.observation.job_hash for job in source_qualified}),
            "employer_attribution_rate": (
                len(attributed) / len(source_observed) if source_observed else 0.0
            ),
            "unique_qualifying_employers": len(unique_employers),
            "novel_employers_vs_baseline": len(unique_employers - known),
            "newest_seen": max(
                (item.observed_at_utc for item in source_observed), default=None
            ),
        }

    novel = [row for row in employers if row["origin_status"] == "novel"]
    return {
        "schema": CENSUS_SCHEMA,
        "authority": "read_only_discovery_evidence",
        "boundary": {
            "database_writes": 0,
            "bronze_writes": 0,
            "silver_writes": 0,
            "product_authority": 0,
            "candidate_creation": 0,
            "connector_activation": 0,
            "matching_job_count_minimum": 1,
        },
        "core_sensors": list(CORE_SENSORS),
        "residual_sensors": list(RESIDUAL_SENSORS),
        "observed_job_count": len(observed),
        "qualifying_job_count": len({job.observation.job_hash for job in qualified}),
        "employer_count": len(employers),
        "novel_employer_count": len(novel),
        "employers": employers,
        "source_metrics": by_source,
    }
