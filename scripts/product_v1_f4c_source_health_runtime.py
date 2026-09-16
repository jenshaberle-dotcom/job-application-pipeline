"""F4C read-only current source-health projection.

Historical ingestion success is run history, not current source health.  This module
keeps lifecycle eligibility, scheduling evidence, run history, current reachability,
evidence freshness and delivery yield as separate dimensions.  It is intentionally
read-only and has no ranking, Top-5, activation or application authority.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _utc(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        current = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        try:
            current = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def load_source_schedule_evidence() -> dict[str, dict[str, object]]:
    """Load recurring-ingestion eligibility without inventing a cadence.

    ``recurring_ingestion_enabled`` proves eligibility for the recurring ingestion
    path.  It does not prove that the Windows scheduler is installed/running and it
    does not define a per-source interval.  Therefore the runtime evidence returned
    here deliberately leaves ``expected_cadence_minutes`` unset.
    """

    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(),
        row_factory=dict_row,
    ) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    "SELECT to_regclass('public.search_profiles') AS relation"
                )
                relation = cur.fetchone()
                if not relation or relation.get("relation") is None:
                    return {}
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'search_profiles'
                          AND column_name = 'recurring_ingestion_enabled'
                    ) AS present
                    """
                )
                column = cur.fetchone()
                if not column or not column.get("present"):
                    return {}
                cur.execute(
                    """
                    SELECT
                        source_name,
                        count(*)::integer AS profile_count,
                        count(*) FILTER (WHERE is_active)::integer AS active_profile_count,
                        count(*) FILTER (
                            WHERE is_active AND recurring_ingestion_enabled
                        )::integer AS recurring_enabled_profile_count
                    FROM search_profiles
                    GROUP BY source_name
                    ORDER BY source_name
                    """
                )
                rows = tuple(cur.fetchall())
        conn.rollback()

    return {
        str(row["source_name"]): {
            "profile_count": int(row["profile_count"] or 0),
            "active_profile_count": int(row["active_profile_count"] or 0),
            "recurring_enabled_profile_count": int(
                row["recurring_enabled_profile_count"] or 0
            ),
            "expected_cadence_minutes": None,
            "cadence_truth_source": None,
        }
        for row in rows
        if str(row.get("source_name") or "").strip()
    }


def _schedule_projection(
    evidence: Mapping[str, object] | None,
) -> dict[str, object]:
    if evidence is None:
        return {
            "status": "unknown",
            "recurring_ingestion_eligible": None,
            "recurring_enabled_profile_count": None,
            "expected_cadence_minutes": None,
            "next_expected_run_at": None,
            "cadence_authority": False,
            "truth_source": "not_projected",
        }

    recurring_count = int(evidence.get("recurring_enabled_profile_count") or 0)
    raw_cadence = evidence.get("expected_cadence_minutes")
    try:
        cadence = int(raw_cadence) if raw_cadence is not None else None
    except (TypeError, ValueError):
        cadence = None
    if cadence is not None and cadence <= 0:
        cadence = None

    cadence_source = str(evidence.get("cadence_truth_source") or "").strip() or None
    cadence_authority = cadence is not None and cadence_source is not None

    if recurring_count <= 0:
        status = "not_scheduled"
    elif cadence_authority:
        status = "scheduled"
    else:
        status = "recurring_enabled_cadence_unknown"

    return {
        "status": status,
        "recurring_ingestion_eligible": recurring_count > 0,
        "recurring_enabled_profile_count": recurring_count,
        "expected_cadence_minutes": cadence if cadence_authority else None,
        "next_expected_run_at": None,
        "cadence_authority": cadence_authority,
        "truth_source": (
            "search_profiles.recurring_ingestion_enabled"
            if not cadence_authority
            else cadence_source
        ),
    }


def _current_health(
    source: Mapping[str, object],
    *,
    schedule: dict[str, object],
    observed_at: datetime,
) -> tuple[dict[str, object], dict[str, object]]:
    old_health = _mapping(source.get("operational_health"))
    ingestion = _mapping(source.get("last_ingestion"))
    latest = str(
        old_health.get("latest_run_status")
        or ingestion.get("status")
        or "unknown"
    ).strip().lower()
    run_at = _utc(ingestion.get("finished_at") or ingestion.get("started_at"))
    age_hours = (
        round(max(0.0, (observed_at - run_at).total_seconds() / 3600.0), 2)
        if run_at is not None
        else None
    )

    cadence = schedule.get("expected_cadence_minutes")
    cadence_minutes = int(cadence) if isinstance(cadence, int) and cadence > 0 else None
    next_expected = (
        run_at + timedelta(minutes=cadence_minutes)
        if run_at is not None and cadence_minutes is not None
        else None
    )
    schedule["next_expected_run_at"] = _iso(next_expected)

    if latest == "failed":
        status = "degraded"
        reason = "latest_attempt_failed"
        freshness = "unknown_without_success"
    elif latest == "running":
        status = "unknown"
        reason = "latest_attempt_in_progress"
        freshness = "unknown"
    elif latest != "success":
        status = "unknown"
        reason = "no_successful_run_current_health_evidence"
        freshness = "unknown"
    elif cadence_minutes is None:
        status = "unknown"
        reason = "successful_run_without_explicit_cadence_authority"
        freshness = "cadence_unknown"
    elif run_at is None:
        status = "unknown"
        reason = "successful_run_timestamp_missing"
        freshness = "unknown"
    elif next_expected is not None and observed_at > next_expected:
        status = "stale"
        reason = "successful_run_overdue_for_explicit_cadence"
        freshness = "overdue"
    else:
        status = "healthy"
        reason = "successful_run_within_explicit_cadence"
        freshness = "within_cadence"

    health = {
        "status": status,
        "reason": reason,
        "latest_run_status": latest,
        "historical_projection_status": str(old_health.get("status") or "unknown"),
        "last_run_at": _iso(run_at),
        "last_run_age_hours": age_hours,
        "freshness_status": freshness,
        "cadence_authority": bool(schedule.get("cadence_authority")),
        "truth_available": bool(old_health.get("truth_available", True)),
        "truth_source": "ingestion_runs + explicit scheduling evidence",
    }
    reachability = {
        "status": "unknown",
        "measured_at": None,
        "reason": "no_current_reachability_measurement",
        "truth_source": "not_measured",
    }
    return health, reachability


def project_current_source_health(
    payload: Mapping[str, object],
    *,
    schedule_evidence: Mapping[str, Mapping[str, object]] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, object]:
    """Return a Product payload with current-health truth projected read-only."""

    current_time = observed_at or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    current_time = current_time.astimezone(timezone.utc)

    result = dict(payload)
    raw_overview = result.get("source_connector_overview")
    if not isinstance(raw_overview, Mapping):
        return result

    overview = dict(raw_overview)
    raw_sources = overview.get("sources")
    if not isinstance(raw_sources, list):
        return result

    schedules = schedule_evidence or {}
    projected_sources: list[object] = []
    health_counts: Counter[str] = Counter()
    latest_success_count = 0
    success_without_cadence_count = 0
    zero_yield_success_count = 0
    reachability_unknown_count = 0

    for raw_source in raw_sources:
        if not isinstance(raw_source, Mapping):
            projected_sources.append(raw_source)
            continue
        source = dict(raw_source)
        source_name = str(source.get("source_name") or "").strip()
        schedule = _schedule_projection(schedules.get(source_name))
        health, reachability = _current_health(
            source,
            schedule=schedule,
            observed_at=current_time,
        )
        ingestion = _mapping(source.get("last_ingestion"))
        latest = str(health.get("latest_run_status") or "unknown")
        loaded = int(ingestion.get("total_loaded") or 0)
        inserted = int(ingestion.get("inserted_count") or 0)
        zero_yield = latest == "success" and loaded == 0

        source["scheduling"] = schedule
        source["operational_health"] = health
        source["reachability"] = reachability
        source["delivery"] = {
            "latest_run_loaded": loaded,
            "latest_run_inserted": inserted,
            "latest_success_zero_yield": zero_yield,
            "truth_source": "ingestion_runs",
        }
        projected_sources.append(source)

        health_counts[str(health["status"])] += 1
        if latest == "success":
            latest_success_count += 1
            if not health["cadence_authority"]:
                success_without_cadence_count += 1
        if zero_yield:
            zero_yield_success_count += 1
        if reachability["status"] == "unknown":
            reachability_unknown_count += 1

    overview["sources"] = projected_sources
    summary = dict(overview.get("summary") or {})
    summary.update(
        {
            "current_health_healthy_count": health_counts["healthy"],
            "current_health_degraded_count": health_counts["degraded"],
            "current_health_stale_count": health_counts["stale"],
            "current_health_unknown_count": health_counts["unknown"],
            "latest_success_count": latest_success_count,
            "latest_success_without_cadence_authority_count": success_without_cadence_count,
            "latest_success_zero_yield_count": zero_yield_success_count,
            "reachability_unknown_count": reachability_unknown_count,
        }
    )
    overview["summary"] = summary
    result["source_connector_overview"] = overview

    boundaries = dict(result.get("boundaries") or {})
    boundaries.update(
        {
            "historical_run_success_is_not_current_source_health": True,
            "missing_cadence_keeps_current_health_unknown": True,
            "recurring_eligibility_is_not_cadence_authority": True,
            "zero_yield_is_not_source_failure": True,
            "current_reachability_requires_current_measurement": True,
            "f4c_source_health_projection_is_read_only": True,
            "f4c_source_health_projection_has_no_ranking_authority": True,
            "f4c_source_health_projection_has_no_application_authority": True,
        }
    )
    result["boundaries"] = boundaries
    return result


__all__ = [
    "load_source_schedule_evidence",
    "project_current_source_health",
]
