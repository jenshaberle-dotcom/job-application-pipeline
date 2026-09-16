"""F4C read-only source/operator evidence projection.

Historical ingestion success, current reachability, scheduling, current job yield and
source-data freshness are separate truths.  The operator-facing projection answers
what a system user can actually act on without inventing a live-health claim from a
historical success or from scheduler cadence.
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


def _age_hours(value: object, *, observed_at: datetime) -> float | None:
    current = _utc(value)
    if current is None:
        return None
    return round(max(0.0, (observed_at - current).total_seconds() / 3600.0), 2)


def load_source_schedule_evidence() -> dict[str, dict[str, object]]:
    """Load recurring-ingestion eligibility without inventing a cadence."""

    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(),
        row_factory=dict_row,
    ) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SELECT to_regclass('public.search_profiles') AS relation")
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


def _relation_exists(cur: psycopg.Cursor[Any], relation_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) AS relation", (f"public.{relation_name}",))
    row = cur.fetchone()
    return bool(row and row.get("relation") is not None)


def load_source_operator_evidence() -> dict[str, dict[str, object]]:
    """Load source-local job evidence for the operator surface, read-only.

    The projection deliberately does not turn absence into vacancy closure.  The
    disappeared count is available only when the latest two source executions are
    both explicitly correlated and fully successful; otherwise it is left unknown.
    """

    evidence: dict[str, dict[str, object]] = {}
    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(),
        row_factory=dict_row,
    ) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                has_runs = _relation_exists(cur, "ingestion_runs")
                has_observations = _relation_exists(cur, "job_observations")
                has_current = _relation_exists(cur, "gold_current_job_opportunities")
                if not has_runs:
                    return {}

                if has_current:
                    cur.execute(
                        """
                        SELECT
                            source_name,
                            count(*)::integer AS current_job_count,
                            max(last_positive_observed_at) AS latest_current_job_observed_at
                        FROM gold_current_job_opportunities
                        GROUP BY source_name
                        """
                    )
                    for row in cur.fetchall():
                        name = str(row.get("source_name") or "").strip()
                        if name:
                            evidence.setdefault(name, {}).update(
                                {
                                    "current_job_count": int(row["current_job_count"] or 0),
                                    "latest_current_job_observed_at": row.get(
                                        "latest_current_job_observed_at"
                                    ),
                                }
                            )

                if has_observations:
                    cur.execute(
                        """
                        SELECT source_name, max(observed_at) AS latest_job_observed_at
                        FROM job_observations
                        WHERE is_seen = TRUE
                        GROUP BY source_name
                        """
                    )
                    for row in cur.fetchall():
                        name = str(row.get("source_name") or "").strip()
                        if name:
                            evidence.setdefault(name, {})["latest_job_observed_at"] = row.get(
                                "latest_job_observed_at"
                            )

                cur.execute(
                    """
                    SELECT DISTINCT ON (source_name)
                        source_name,
                        coalesce(finished_at, started_at) AS delivered_at,
                        total_loaded,
                        inserted_count
                    FROM ingestion_runs
                    WHERE status = 'success'
                      AND total_loaded > 0
                    ORDER BY source_name, coalesce(finished_at, started_at) DESC, id DESC
                    """
                )
                for row in cur.fetchall():
                    name = str(row.get("source_name") or "").strip()
                    if name:
                        evidence.setdefault(name, {}).update(
                            {
                                "last_job_delivery_at": row.get("delivered_at"),
                                "last_job_delivery_loaded": int(row["total_loaded"] or 0),
                                "last_job_delivery_inserted": int(row["inserted_count"] or 0),
                            }
                        )

                if has_observations:
                    cur.execute(
                        """
                        WITH successful_executions AS (
                            SELECT
                                source_name,
                                execution_id,
                                max(coalesce(finished_at, started_at)) AS finished_at
                            FROM ingestion_runs
                            WHERE execution_id IS NOT NULL
                            GROUP BY source_name, execution_id
                            HAVING bool_and(status = 'success')
                        ), ranked AS (
                            SELECT
                                source_name,
                                execution_id,
                                finished_at,
                                row_number() OVER (
                                    PARTITION BY source_name
                                    ORDER BY finished_at DESC, execution_id DESC
                                ) AS position
                            FROM successful_executions
                        )
                        SELECT source_name, execution_id, finished_at, position
                        FROM ranked
                        WHERE position <= 2
                        ORDER BY source_name, position
                        """
                    )
                    ranked = [dict(row) for row in cur.fetchall()]
                    pair_by_source: dict[str, dict[int, dict[str, object]]] = {}
                    for row in ranked:
                        name = str(row.get("source_name") or "").strip()
                        if not name:
                            continue
                        pair_by_source.setdefault(name, {})[int(row["position"])] = row

                    for name, pair in pair_by_source.items():
                        latest = pair.get(1)
                        previous = pair.get(2)
                        target = evidence.setdefault(name, {})
                        if latest is None or previous is None:
                            target["disappeared_comparison_available"] = False
                            target["disappeared_comparison_reason"] = (
                                "two_successful_correlated_executions_required"
                            )
                            continue
                        cur.execute(
                            """
                            SELECT DISTINCT
                                coalesce(
                                    nullif(btrim(observation.external_job_id), ''),
                                    nullif(btrim(observation.source_url), '')
                                ) AS identity
                            FROM job_observations observation
                            JOIN ingestion_runs run
                              ON run.id = observation.ingestion_run_id
                            WHERE run.source_name = %s
                              AND run.execution_id = %s
                              AND observation.is_seen = TRUE
                            """,
                            (name, previous["execution_id"]),
                        )
                        previous_ids = {
                            str(row["identity"])
                            for row in cur.fetchall()
                            if row.get("identity") is not None
                        }
                        cur.execute(
                            """
                            SELECT DISTINCT
                                coalesce(
                                    nullif(btrim(observation.external_job_id), ''),
                                    nullif(btrim(observation.source_url), '')
                                ) AS identity
                            FROM job_observations observation
                            JOIN ingestion_runs run
                              ON run.id = observation.ingestion_run_id
                            WHERE run.source_name = %s
                              AND run.execution_id = %s
                              AND observation.is_seen = TRUE
                            """,
                            (name, latest["execution_id"]),
                        )
                        current_ids = {
                            str(row["identity"])
                            for row in cur.fetchall()
                            if row.get("identity") is not None
                        }
                        target.update(
                            {
                                "disappeared_comparison_available": True,
                                "disappeared_since_previous_success": len(
                                    previous_ids - current_ids
                                ),
                                "previous_successful_execution_at": previous.get(
                                    "finished_at"
                                ),
                                "current_successful_execution_at": latest.get("finished_at"),
                                "previous_execution_job_count": len(previous_ids),
                                "current_execution_job_count": len(current_ids),
                            }
                        )
        conn.rollback()
    return evidence


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
    """Keep the internal freshness contract for diagnostics, not primary UX."""

    old_health = _mapping(source.get("operational_health"))
    ingestion = _mapping(source.get("last_ingestion"))
    latest = str(
        old_health.get("latest_run_status") or ingestion.get("status") or "unknown"
    ).strip().lower()
    run_at = _utc(ingestion.get("finished_at") or ingestion.get("started_at"))
    age_hours = _age_hours(run_at, observed_at=observed_at)

    cadence = schedule.get("expected_cadence_minutes")
    cadence_minutes = int(cadence) if isinstance(cadence, int) and cadence > 0 else None
    next_expected = (
        run_at + timedelta(minutes=cadence_minutes)
        if run_at is not None and cadence_minutes is not None
        else None
    )
    schedule["next_expected_run_at"] = _iso(next_expected)

    if latest == "failed":
        status, reason, freshness = "degraded", "latest_attempt_failed", "unknown_without_success"
    elif latest == "running":
        status, reason, freshness = "unknown", "latest_attempt_in_progress", "unknown"
    elif latest != "success":
        status, reason, freshness = (
            "unknown",
            "no_successful_run_current_health_evidence",
            "unknown",
        )
    elif cadence_minutes is None:
        status, reason, freshness = (
            "unknown",
            "successful_run_without_explicit_cadence_authority",
            "cadence_unknown",
        )
    elif run_at is None:
        status, reason, freshness = "unknown", "successful_run_timestamp_missing", "unknown"
    elif next_expected is not None and observed_at > next_expected:
        status, reason, freshness = (
            "stale",
            "successful_run_overdue_for_explicit_cadence",
            "overdue",
        )
    else:
        status, reason, freshness = (
            "healthy",
            "successful_run_within_explicit_cadence",
            "within_cadence",
        )

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
        "status": "not_checked",
        "measured_at": None,
        "reason": "no_live_source_check_recorded",
        "truth_source": "not_measured",
    }
    return health, reachability


def _scan_status(latest: str) -> tuple[str, str]:
    if latest == "success":
        return "ok", "latest_source_scan_succeeded"
    if latest == "failed":
        return "failed", "latest_source_scan_failed"
    if latest == "running":
        return "running", "source_scan_in_progress"
    if latest == "not_run":
        return "not_scanned", "no_source_scan_recorded"
    return "unknown", "source_scan_status_unknown"


def project_current_source_health(
    payload: Mapping[str, object],
    *,
    schedule_evidence: Mapping[str, Mapping[str, object]] | None = None,
    operator_evidence: Mapping[str, Mapping[str, object]] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, object]:
    """Return the Product payload with read-only source operator evidence."""

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
    operator_rows = (
        load_source_operator_evidence()
        if operator_evidence is None
        else operator_evidence
    )
    projected_sources: list[object] = []
    health_counts: Counter[str] = Counter()
    scan_counts: Counter[str] = Counter()
    latest_success_count = 0
    success_without_cadence_count = 0
    zero_yield_success_count = 0
    reachability_not_checked_count = 0
    disappeared_comparable_count = 0

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
        operator = _mapping(operator_rows.get(source_name))
        latest_observed = operator.get("latest_job_observed_at")
        scan_status, scan_reason = _scan_status(latest)

        source["scheduling"] = schedule
        source["operational_health"] = health
        source["source_scan"] = {
            "status": scan_status,
            "reason": scan_reason,
            "result": latest,
            "finished_at": health.get("last_run_at"),
            "truth_source": "ingestion_runs",
        }
        source["reachability"] = reachability
        source["delivery"] = {
            "latest_run_loaded": loaded,
            "latest_run_inserted": inserted,
            "latest_success_zero_yield": zero_yield,
            "current_job_count": int(operator.get("current_job_count") or 0),
            "last_job_delivery_at": _iso(_utc(operator.get("last_job_delivery_at"))),
            "last_job_delivery_loaded": int(
                operator.get("last_job_delivery_loaded") or 0
            ),
            "last_job_delivery_inserted": int(
                operator.get("last_job_delivery_inserted") or 0
            ),
            "latest_job_observed_at": _iso(_utc(latest_observed)),
            "source_data_age_hours": _age_hours(
                latest_observed,
                observed_at=current_time,
            ),
            "disappeared_comparison_available": bool(
                operator.get("disappeared_comparison_available")
            ),
            "disappeared_since_previous_success": (
                int(operator.get("disappeared_since_previous_success") or 0)
                if operator.get("disappeared_comparison_available") is True
                else None
            ),
            "previous_successful_execution_at": _iso(
                _utc(operator.get("previous_successful_execution_at"))
            ),
            "current_successful_execution_at": _iso(
                _utc(operator.get("current_successful_execution_at"))
            ),
            "disappeared_comparison_reason": operator.get(
                "disappeared_comparison_reason"
            ),
            "truth_source": (
                "ingestion_runs + job_observations + gold_current_job_opportunities"
            ),
        }
        projected_sources.append(source)

        health_counts[str(health["status"])] += 1
        scan_counts[scan_status] += 1
        if latest == "success":
            latest_success_count += 1
            if not health["cadence_authority"]:
                success_without_cadence_count += 1
        if zero_yield:
            zero_yield_success_count += 1
        if reachability["status"] == "not_checked":
            reachability_not_checked_count += 1
        if operator.get("disappeared_comparison_available") is True:
            disappeared_comparable_count += 1

    overview["sources"] = projected_sources
    summary = dict(overview.get("summary") or {})
    summary.update(
        {
            "current_health_healthy_count": health_counts["healthy"],
            "current_health_degraded_count": health_counts["degraded"],
            "current_health_stale_count": health_counts["stale"],
            "current_health_unknown_count": health_counts["unknown"],
            "latest_scan_ok_count": scan_counts["ok"],
            "latest_scan_failed_count": scan_counts["failed"],
            "latest_scan_running_count": scan_counts["running"],
            "latest_scan_not_scanned_count": scan_counts["not_scanned"],
            "latest_success_count": latest_success_count,
            "latest_success_without_cadence_authority_count": success_without_cadence_count,
            "latest_success_zero_yield_count": zero_yield_success_count,
            "reachability_not_checked_count": reachability_not_checked_count,
            "reachability_unknown_count": reachability_not_checked_count,
            "disappeared_comparable_source_count": disappeared_comparable_count,
        }
    )
    overview["summary"] = summary
    result["source_connector_overview"] = overview

    boundaries = dict(result.get("boundaries") or {})
    boundaries.update(
        {
            "historical_run_success_is_not_current_source_health": True,
            "missing_cadence_keeps_internal_freshness_unknown": True,
            "recurring_eligibility_is_not_cadence_authority": True,
            "zero_yield_is_not_source_failure": True,
            "current_reachability_requires_current_measurement": True,
            "source_scan_result_is_not_live_reachability": True,
            "disappeared_count_requires_two_successful_correlated_executions": True,
            "f4c_source_health_projection_is_read_only": True,
            "f4c_source_health_projection_has_no_ranking_authority": True,
            "f4c_source_health_projection_has_no_application_authority": True,
        }
    )
    result["boundaries"] = boundaries
    return result


__all__ = [
    "load_source_operator_evidence",
    "load_source_schedule_evidence",
    "project_current_source_health",
]
