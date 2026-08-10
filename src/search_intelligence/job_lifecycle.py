"""Fail-closed domain contract for vacancy lifecycle health evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping


HEALTH_OUTCOMES = frozenset(
    {"seen_active", "not_seen", "closed", "unverifiable"}
)
HEALTH_COVERAGES = frozenset(
    {"exact_detail", "complete_inventory", "partial_listing", "unknown"}
)
LIFECYCLE_STATES = frozenset(
    {
        "active_confirmed",
        "stale_needs_refresh",
        "inactive_confirmed",
        "unverifiable",
    }
)


@dataclass(frozen=True)
class JobHealthObservation:
    raw_job_id: int
    source_name: str
    outcome: str
    coverage: str
    evidence_reason: str
    observed_by: str
    observed_at: datetime
    external_job_id: str | None = None
    source_url: str | None = None
    evidence: Mapping[str, object] = field(default_factory=dict)


def validate_job_health_observation(
    observation: JobHealthObservation,
) -> JobHealthObservation:
    """Validate one sensor observation without inventing source authority."""
    if observation.raw_job_id <= 0:
        raise ValueError("raw_job_id must be positive")
    if not observation.source_name.strip():
        raise ValueError("source_name must not be blank")
    if observation.outcome not in HEALTH_OUTCOMES:
        raise ValueError(f"unsupported health outcome: {observation.outcome}")
    if observation.coverage not in HEALTH_COVERAGES:
        raise ValueError(f"unsupported health coverage: {observation.coverage}")
    if not observation.evidence_reason.strip():
        raise ValueError("evidence_reason must not be blank")
    if not observation.observed_by.strip():
        raise ValueError("observed_by must not be blank")
    if observation.outcome == "closed" and observation.coverage != "exact_detail":
        raise ValueError("closed outcome requires exact_detail coverage")
    if observation.observed_at.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware")
    return observation


def resolve_job_lifecycle(
    latest_health: JobHealthObservation | None,
    *,
    last_positive_observed_at: datetime | None = None,
    freshness_cutoff: datetime | None = None,
) -> str:
    """Resolve lifecycle truth from explicit health evidence.

    Historical positive observations are retained as evidence but do not by
    themselves establish a current health baseline. Once explicit health evidence
    exists, a later source-local positive observation can reactivate the vacancy.
    A caller may later supply an operator-approved freshness cutoff; this module
    deliberately does not choose one.
    """
    if latest_health is None:
        return "stale_needs_refresh"

    validate_job_health_observation(latest_health)

    if (
        last_positive_observed_at is not None
        and last_positive_observed_at.tzinfo is None
    ):
        raise ValueError("last_positive_observed_at must be timezone-aware")
    if freshness_cutoff is not None and freshness_cutoff.tzinfo is None:
        raise ValueError("freshness_cutoff must be timezone-aware")

    effective_checked_at = latest_health.observed_at
    if (
        last_positive_observed_at is not None
        and last_positive_observed_at > latest_health.observed_at
    ):
        state = "active_confirmed"
        effective_checked_at = last_positive_observed_at
    elif latest_health.outcome == "seen_active":
        state = "active_confirmed"
    elif (
        latest_health.outcome == "closed"
        and latest_health.coverage == "exact_detail"
    ):
        state = "inactive_confirmed"
    elif (
        latest_health.outcome == "not_seen"
        and latest_health.coverage == "complete_inventory"
    ):
        state = "inactive_confirmed"
    else:
        state = "unverifiable"

    if (
        state == "active_confirmed"
        and freshness_cutoff is not None
        and effective_checked_at < freshness_cutoff
    ):
        return "stale_needs_refresh"
    return state


def effective_product_activity(lifecycle_status: str) -> str:
    """Map lifecycle truth into the existing Product V1 activity vocabulary."""
    if lifecycle_status not in LIFECYCLE_STATES:
        raise ValueError(f"unsupported lifecycle status: {lifecycle_status}")
    if lifecycle_status == "active_confirmed":
        return "active"
    if lifecycle_status == "inactive_confirmed":
        return "inactive"
    return "unknown"
