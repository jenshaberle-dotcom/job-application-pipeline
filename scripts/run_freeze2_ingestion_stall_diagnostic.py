"""Read-only Freeze-II diagnosis for stalled recurring ingestion.

The report distinguishes a scheduler/wrapper gap from source zero-yield,
source failures, Bronze persistence, and Silver normalization lag. It performs
no external requests and no database writes.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config


SCHEMA = "job_application_pipeline.freeze2_ingestion_stall_diagnostic.v1"


def _fetch_one(cur: psycopg.Cursor[Any], sql: str, params: tuple[object, ...] = ()) -> dict[str, Any]:
    cur.execute(sql, params)
    row = cur.fetchone()
    return dict(row) if row else {}


def _fetch_all(cur: psycopg.Cursor[Any], sql: str, params: tuple[object, ...] = ()) -> list[dict[str, Any]]:
    cur.execute(sql, params)
    return [dict(row) for row in cur.fetchall()]


def _age_hours(value: object, *, now: datetime) -> float | None:
    if not isinstance(value, datetime):
        return None
    observed = value if value.tzinfo else value.replace(tzinfo=UTC)
    return round((now - observed.astimezone(UTC)).total_seconds() / 3600.0, 2)


def _classify(
    *,
    recurring_profile_count: int,
    latest_run: dict[str, Any],
    recent_failed_run_count: int,
    latest_bronze: datetime | None,
    latest_silver: datetime | None,
    now: datetime,
) -> tuple[str, str]:
    latest_started = latest_run.get("started_at")
    run_age = _age_hours(latest_started, now=now)
    bronze_age = _age_hours(latest_bronze, now=now)
    silver_age = _age_hours(latest_silver, now=now)

    if recurring_profile_count == 0:
        return (
            "no_recurring_profiles",
            "No active recurring-ingestion profiles exist; the daily runner has nothing eligible to execute.",
        )

    if latest_started is None or run_age is None or run_age > 36:
        return (
            "scheduler_or_wrapper_not_running",
            "Recurring profiles exist but no ingestion run started within 36 hours. Inspect the Windows Task Scheduler/watchdog wrapper before changing source logic.",
        )

    if recent_failed_run_count > 0 and str(latest_run.get("status") or "") != "success":
        return (
            "ingestion_latest_run_failed",
            "The scheduler is producing runs, but the latest ingestion failed. Inspect the latest error_type/error_stage/error_message.",
        )

    if bronze_age is None or bronze_age > 36:
        return (
            "recent_runs_without_new_bronze",
            "Ingestion runs are recent but no new Bronze row/observation is recent. Distinguish legitimate zero-yield/duplicates from source suppression or connector failures.",
        )

    if silver_age is None or (bronze_age is not None and silver_age - bronze_age > 12):
        return (
            "silver_processing_lag",
            "Bronze is fresher than Silver by more than the bounded diagnostic threshold. Inspect the Silver stage of the daily pipeline.",
        )

    return (
        "pipeline_recent",
        "Scheduler, ingestion and Bronze/Silver timestamps are recent. A stale current-cohort freshness card may then reflect cohort membership rather than a stopped pipeline.",
    )


def build_report() -> dict[str, Any]:
    now = datetime.now(UTC)
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")

                profile_summary = _fetch_one(
                    cur,
                    """
                    SELECT
                        count(*) FILTER (WHERE is_active)::integer AS active_profile_count,
                        count(*) FILTER (
                            WHERE is_active
                              AND COALESCE(recurring_ingestion_enabled, TRUE)
                        )::integer AS recurring_profile_count
                    FROM search_profiles
                    """,
                )

                latest_run = _fetch_one(
                    cur,
                    """
                    SELECT
                        ir.id,
                        ir.source_name,
                        sp.profile_name,
                        ir.status,
                        ir.started_at,
                        ir.finished_at,
                        ir.total_loaded,
                        ir.inserted_count,
                        ir.duplicate_count,
                        ir.error_type,
                        ir.error_stage,
                        ir.error_message
                    FROM ingestion_runs ir
                    LEFT JOIN search_profiles sp ON sp.id = ir.search_profile_id
                    ORDER BY ir.started_at DESC, ir.id DESC
                    LIMIT 1
                    """,
                )

                recent = _fetch_one(
                    cur,
                    """
                    SELECT
                        count(*) FILTER (
                            WHERE started_at >= NOW() - INTERVAL '36 hours'
                        )::integer AS run_count_36h,
                        count(*) FILTER (
                            WHERE started_at >= NOW() - INTERVAL '36 hours'
                              AND status = 'success'
                        )::integer AS success_count_36h,
                        count(*) FILTER (
                            WHERE started_at >= NOW() - INTERVAL '36 hours'
                              AND status <> 'success'
                        )::integer AS failed_count_36h,
                        COALESCE(sum(total_loaded) FILTER (
                            WHERE started_at >= NOW() - INTERVAL '36 hours'
                        ), 0)::integer AS loaded_36h,
                        COALESCE(sum(inserted_count) FILTER (
                            WHERE started_at >= NOW() - INTERVAL '36 hours'
                        ), 0)::integer AS inserted_36h,
                        COALESCE(sum(duplicate_count) FILTER (
                            WHERE started_at >= NOW() - INTERVAL '36 hours'
                        ), 0)::integer AS duplicates_36h
                    FROM ingestion_runs
                    """,
                )

                latest_layers = _fetch_one(
                    cur,
                    """
                    SELECT
                        (SELECT max(created_at) FROM raw_jobs) AS latest_raw_created_at,
                        (SELECT max(fetched_at) FROM raw_jobs) AS latest_raw_fetched_at,
                        (SELECT max(observed_at) FROM job_observations WHERE is_seen = TRUE)
                            AS latest_observation_at,
                        (SELECT max(normalized_at) FROM silver_jobs)
                            AS latest_silver_normalized_at,
                        (SELECT max(assessed_at) FROM job_product_assessments)
                            AS latest_gold_assessed_at
                    """,
                )

                profiles = _fetch_all(
                    cur,
                    """
                    SELECT
                        sp.id,
                        sp.profile_name,
                        sp.source_name,
                        sp.is_active,
                        COALESCE(sp.recurring_ingestion_enabled, TRUE)
                            AS recurring_ingestion_enabled,
                        latest.status AS latest_status,
                        latest.started_at AS latest_started_at,
                        latest.finished_at AS latest_finished_at,
                        latest.total_loaded AS latest_total_loaded,
                        latest.inserted_count AS latest_inserted_count,
                        latest.duplicate_count AS latest_duplicate_count,
                        latest.error_type,
                        latest.error_stage,
                        latest.error_message
                    FROM search_profiles sp
                    LEFT JOIN LATERAL (
                        SELECT ir.*
                        FROM ingestion_runs ir
                        WHERE ir.search_profile_id = sp.id
                        ORDER BY ir.started_at DESC, ir.id DESC
                        LIMIT 1
                    ) latest ON TRUE
                    WHERE sp.is_active
                    ORDER BY sp.source_name, sp.profile_name
                    """,
                )

                latest_failures = _fetch_all(
                    cur,
                    """
                    SELECT
                        ir.id,
                        ir.source_name,
                        COALESCE(sp.profile_name, '<unknown>') AS profile_name,
                        ir.status,
                        ir.started_at,
                        ir.finished_at,
                        ir.error_type,
                        ir.error_stage,
                        ir.error_message
                    FROM ingestion_runs ir
                    LEFT JOIN search_profiles sp ON sp.id = ir.search_profile_id
                    WHERE ir.status <> 'success'
                    ORDER BY ir.started_at DESC, ir.id DESC
                    LIMIT 10
                    """,
                )
        conn.rollback()

    recurring = int(profile_summary.get("recurring_profile_count") or 0)
    failed_recent = int(recent.get("failed_count_36h") or 0)
    latest_bronze = latest_layers.get("latest_observation_at") or latest_layers.get("latest_raw_created_at")
    latest_silver = latest_layers.get("latest_silver_normalized_at")
    classification, next_action = _classify(
        recurring_profile_count=recurring,
        latest_run=latest_run,
        recent_failed_run_count=failed_recent,
        latest_bronze=latest_bronze if isinstance(latest_bronze, datetime) else None,
        latest_silver=latest_silver if isinstance(latest_silver, datetime) else None,
        now=now,
    )

    return {
        "schema": SCHEMA,
        "generated_at_utc": now.isoformat(),
        "mode": "read_only",
        "classification": classification,
        "next_action": next_action,
        "profile_summary": profile_summary,
        "latest_ingestion_run": latest_run,
        "recent_36h": recent,
        "layer_freshness": latest_layers,
        "active_profiles": profiles,
        "latest_failures": latest_failures,
        "ages_hours": {
            "latest_ingestion_run": _age_hours(latest_run.get("started_at"), now=now),
            "latest_bronze": _age_hours(latest_bronze, now=now),
            "latest_silver": _age_hours(latest_silver, now=now),
            "latest_gold": _age_hours(latest_layers.get("latest_gold_assessed_at"), now=now),
        },
        "boundaries": {
            "database_writes": 0,
            "external_requests": 0,
            "source_activation": 0,
            "scheduler_mutation": 0,
            "product_mutation": 0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/freeze2-ingestion-stall-diagnostic.json"),
    )
    args = parser.parse_args(argv)
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    print("============================================")
    print("FREEZE-II INGESTION STALL DIAGNOSTIC")
    print("============================================")
    print(f"CLASSIFICATION={report['classification']}")
    print(f"NEXT_ACTION={report['next_action']}")
    print("PROFILE_SUMMARY=" + json.dumps(report["profile_summary"], default=str, sort_keys=True))
    print("LATEST_RUN=" + json.dumps(report["latest_ingestion_run"], default=str, sort_keys=True))
    print("RECENT_36H=" + json.dumps(report["recent_36h"], default=str, sort_keys=True))
    print("LAYER_FRESHNESS=" + json.dumps(report["layer_freshness"], default=str, sort_keys=True))
    print("AGES_HOURS=" + json.dumps(report["ages_hours"], default=str, sort_keys=True))
    print("DATABASE_WRITES=0")
    print("EXTERNAL_REQUESTS=0")
    print(f"artifact={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
