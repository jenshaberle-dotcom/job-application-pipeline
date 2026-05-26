"""Create persistent source-value metric snapshots.

This script stores one snapshot row per current source_name. It intentionally
uses the current operational semantics and does not calculate lifecycle scores
or connector recommendations yet.

Usage:
    python -m scripts.create_source_value_snapshot
    python -m scripts.create_source_value_snapshot --reason manual_block_e
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from src.config import get_database_config


SOURCE_VALUE_SQL = """
WITH source_names AS (
    SELECT source_name FROM search_profiles WHERE is_active = TRUE
    UNION
    SELECT source_name FROM ingestion_runs
    UNION
    SELECT rj.source_name
    FROM raw_jobs rj
    WHERE rj.ingestion_run_id IS NOT NULL
       OR rj.search_profile_id IS NOT NULL
    UNION
    SELECT source_name FROM silver_jobs
),
key_groups AS (
    SELECT
        canonical_key_candidate,
        COUNT(*) AS row_count,
        COUNT(DISTINCT source_name) AS source_count
    FROM silver_jobs
    WHERE canonical_key_candidate IS NOT NULL
    GROUP BY canonical_key_candidate
),
run_base AS (
    SELECT
        source_name,
        COUNT(*) AS ingestion_runs,
        COUNT(*) FILTER (WHERE status = 'success') AS successful_runs,
        COUNT(*) FILTER (WHERE status <> 'success') AS failed_runs,
        COALESCE(SUM(total_loaded), 0) AS matched_jobs_after_filter,
        COALESCE(SUM(inserted_count), 0) AS inserted_jobs,
        COALESCE(SUM(duplicate_count), 0) AS duplicate_jobs,
        MIN(started_at) AS evaluation_window_started_at,
        MAX(finished_at) AS evaluation_window_finished_at
    FROM ingestion_runs
    GROUP BY source_name
),
raw_base AS (
    SELECT
        source_name,
        COUNT(*) AS raw_jobs
    FROM raw_jobs
    WHERE ingestion_run_id IS NOT NULL
       OR search_profile_id IS NOT NULL
    GROUP BY source_name
),
silver_base AS (
    SELECT
        source_name,
        COUNT(*) AS silver_jobs,
        COUNT(DISTINCT normalized_company_name)
            FILTER (WHERE normalized_company_name IS NOT NULL) AS distinct_companies,
        COUNT(DISTINCT canonical_key_candidate)
            FILTER (WHERE canonical_key_candidate IS NOT NULL) AS distinct_candidate_keys,
        COUNT(*) FILTER (WHERE title IS NOT NULL) AS with_title,
        COUNT(*) FILTER (WHERE company_name IS NOT NULL) AS with_company,
        COUNT(*) FILTER (WHERE normalized_location IS NOT NULL) AS with_normalized_location,
        COUNT(*) FILTER (WHERE publication_date IS NOT NULL) AS with_publication_date
    FROM silver_jobs
    GROUP BY source_name
),
source_overlap AS (
    SELECT
        s.source_name,
        COUNT(*) FILTER (WHERE kg.row_count > 1) AS rows_in_duplicate_candidate_groups,
        COUNT(*) FILTER (WHERE kg.source_count > 1) AS rows_in_cross_source_candidate_groups,
        COUNT(DISTINCT s.canonical_key_candidate)
            FILTER (WHERE kg.source_count > 1) AS cross_source_candidate_keys
    FROM silver_jobs s
    LEFT JOIN key_groups kg
        ON kg.canonical_key_candidate = s.canonical_key_candidate
    GROUP BY s.source_name
)
SELECT
    sn.source_name,
    rb.evaluation_window_started_at,
    rb.evaluation_window_finished_at,
    COALESCE(rb.ingestion_runs, 0) AS ingestion_runs,
    COALESCE(rb.successful_runs, 0) AS successful_runs,
    COALESCE(rb.failed_runs, 0) AS failed_runs,
    NULL::INTEGER AS fetched_jobs_before_filter,
    COALESCE(rb.matched_jobs_after_filter, 0) AS matched_jobs_after_filter,
    COALESCE(rb.inserted_jobs, 0) AS inserted_jobs,
    COALESCE(rb.duplicate_jobs, 0) AS duplicate_jobs,
    COALESCE(raw.raw_jobs, 0) AS raw_jobs,
    COALESCE(sb.silver_jobs, 0) AS silver_jobs,
    COALESCE(sb.distinct_companies, 0) AS distinct_companies,
    COALESCE(sb.distinct_candidate_keys, 0) AS distinct_candidate_keys,
    COALESCE(so.rows_in_duplicate_candidate_groups, 0)
        AS rows_in_duplicate_candidate_groups,
    COALESCE(so.rows_in_cross_source_candidate_groups, 0)
        AS rows_in_cross_source_candidate_groups,
    COALESCE(so.cross_source_candidate_keys, 0)
        AS cross_source_candidate_keys,
    ROUND(100.0 * sb.with_title / NULLIF(sb.silver_jobs, 0), 2)
        AS title_completeness_pct,
    ROUND(100.0 * sb.with_company / NULLIF(sb.silver_jobs, 0), 2)
        AS company_completeness_pct,
    ROUND(100.0 * sb.with_normalized_location / NULLIF(sb.silver_jobs, 0), 2)
        AS location_completeness_pct,
    ROUND(100.0 * sb.with_publication_date / NULLIF(sb.silver_jobs, 0), 2)
        AS publication_date_completeness_pct,
    NULL::NUMERIC AS matched_rate_pct,
    ROUND(
        100.0 * COALESCE(rb.duplicate_jobs, 0)
        / NULLIF(COALESCE(rb.matched_jobs_after_filter, 0), 0),
        2
    ) AS duplicate_rate_pct,
    ROUND(
        100.0 * COALESCE(rb.failed_runs, 0)
        / NULLIF(COALESCE(rb.ingestion_runs, 0), 0),
        2
    ) AS failure_rate_pct
FROM source_names sn
LEFT JOIN run_base rb
    ON rb.source_name = sn.source_name
LEFT JOIN raw_base raw
    ON raw.source_name = sn.source_name
LEFT JOIN silver_base sb
    ON sb.source_name = sn.source_name
LEFT JOIN source_overlap so
    ON so.source_name = sn.source_name
ORDER BY sn.source_name;
"""


INSERT_SQL = """
INSERT INTO source_value_snapshots (
    snapshot_reason,
    source_name,
    source_family,
    source_target,
    source_type,
    evaluation_window_started_at,
    evaluation_window_finished_at,
    ingestion_runs,
    successful_runs,
    failed_runs,
    fetched_jobs_before_filter,
    matched_jobs_after_filter,
    inserted_jobs,
    duplicate_jobs,
    raw_jobs,
    silver_jobs,
    distinct_companies,
    distinct_candidate_keys,
    rows_in_duplicate_candidate_groups,
    rows_in_cross_source_candidate_groups,
    cross_source_candidate_keys,
    title_completeness_pct,
    company_completeness_pct,
    location_completeness_pct,
    publication_date_completeness_pct,
    matched_rate_pct,
    duplicate_rate_pct,
    failure_rate_pct,
    source_value_score,
    lifecycle_state,
    recommendation,
    notes,
    metrics
)
VALUES (
    %(snapshot_reason)s,
    %(source_name)s,
    %(source_family)s,
    %(source_target)s,
    %(source_type)s,
    %(evaluation_window_started_at)s,
    %(evaluation_window_finished_at)s,
    %(ingestion_runs)s,
    %(successful_runs)s,
    %(failed_runs)s,
    %(fetched_jobs_before_filter)s,
    %(matched_jobs_after_filter)s,
    %(inserted_jobs)s,
    %(duplicate_jobs)s,
    %(raw_jobs)s,
    %(silver_jobs)s,
    %(distinct_companies)s,
    %(distinct_candidate_keys)s,
    %(rows_in_duplicate_candidate_groups)s,
    %(rows_in_cross_source_candidate_groups)s,
    %(cross_source_candidate_keys)s,
    %(title_completeness_pct)s,
    %(company_completeness_pct)s,
    %(location_completeness_pct)s,
    %(publication_date_completeness_pct)s,
    %(matched_rate_pct)s,
    %(duplicate_rate_pct)s,
    %(failure_rate_pct)s,
    %(source_value_score)s,
    %(lifecycle_state)s,
    %(recommendation)s,
    %(notes)s,
    %(metrics)s
)
RETURNING id;
"""


def source_family(source_name: str) -> str:
    return source_name.split(":", 1)[0]


def source_target(source_name: str) -> str | None:
    if ":" not in source_name:
        return None

    return source_name.split(":", 1)[1]


def source_type(source_name: str) -> str:
    family = source_family(source_name)

    if family == "bundesagentur_fuer_arbeit":
        return "official_api"

    if family == "stepstone":
        return "commercial_aggregator"

    if family in {"greenhouse", "personio"}:
        return "ats_company_board"

    return "unknown"


def format_value(value: Any) -> str:
    if value is None:
        return ""

    return str(value)


def print_table(headers: list[str], rows: Sequence[Sequence[Any]]) -> None:
    if not rows:
        print("No rows.")
        return

    widths = [
        max(len(header), *(len(format_value(row[index])) for row in rows))
        for index, header in enumerate(headers)
    ]

    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))

    for row in rows:
        print(
            " | ".join(
                format_value(value).ljust(widths[index])
                for index, value in enumerate(row)
            )
        )


def build_metrics_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_version": 1,
        "source_value_semantics": {
            "fetched_jobs_before_filter": "not_yet_persisted",
            "matched_jobs_after_filter": "ingestion_runs.total_loaded_under_current_filtering_semantics",
            "source_value_score": "not_yet_calculated",
            "lifecycle_state": "not_yet_calculated",
            "recommendation": "not_yet_calculated",
        },
        "raw_counts": {
            "ingestion_runs": row["ingestion_runs"],
            "successful_runs": row["successful_runs"],
            "failed_runs": row["failed_runs"],
            "raw_jobs": row["raw_jobs"],
            "silver_jobs": row["silver_jobs"],
        },
    }


def build_insert_payload(row: dict[str, Any], snapshot_reason: str) -> dict[str, Any]:
    payload = dict(row)
    payload["snapshot_reason"] = snapshot_reason
    payload["source_family"] = source_family(row["source_name"])
    payload["source_target"] = source_target(row["source_name"])
    payload["source_type"] = source_type(row["source_name"])
    payload["source_value_score"] = None
    payload["lifecycle_state"] = None
    payload["recommendation"] = None
    payload["notes"] = None
    payload["metrics"] = Json(build_metrics_payload(row))
    return payload


def load_source_value_rows(connection: psycopg.Connection) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(SOURCE_VALUE_SQL)
        return list(cursor.fetchall())


def create_snapshots(snapshot_reason: str, dry_run: bool) -> list[dict[str, Any]]:
    config = get_database_config()

    with psycopg.connect(**config) as connection:
        rows = load_source_value_rows(connection)

        if dry_run:
            return rows

        created_rows: list[dict[str, Any]] = []

        with connection.cursor() as cursor:
            for row in rows:
                payload = build_insert_payload(
                    row=dict(row),
                    snapshot_reason=snapshot_reason,
                )
                cursor.execute(INSERT_SQL, payload)
                snapshot_id = cursor.fetchone()[0]
                created = dict(row)
                created["snapshot_id"] = snapshot_id
                created["source_family"] = payload["source_family"]
                created["source_target"] = payload["source_target"]
                created["source_type"] = payload["source_type"]
                created_rows.append(created)

        connection.commit()
        return created_rows


def print_snapshot_summary(rows: list[dict[str, Any]], dry_run: bool) -> None:
    title = "Source Value Snapshot Preview" if dry_run else "Created Source Value Snapshots"

    print()
    print(f"=== {title} ===")
    print()

    table_rows: list[list[Any]] = []
    for row in rows:
        table_rows.append(
            [
                row.get("snapshot_id", ""),
                row["source_name"],
                row.get("source_family") or source_family(row["source_name"]),
                row.get("source_target") or source_target(row["source_name"]),
                row.get("source_type") or source_type(row["source_name"]),
                row["ingestion_runs"],
                row["failed_runs"],
                row["matched_jobs_after_filter"],
                row["inserted_jobs"],
                row["duplicate_jobs"],
                row["raw_jobs"],
                row["silver_jobs"],
                row["distinct_companies"],
                row["distinct_candidate_keys"],
            ]
        )

    print_table(
        headers=[
            "snapshot_id",
            "source_name",
            "family",
            "target",
            "type",
            "runs",
            "failed",
            "matched",
            "inserted",
            "duplicates",
            "raw",
            "silver",
            "companies",
            "candidate_keys",
        ],
        rows=table_rows,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reason",
        default="manual",
        help="Reason stored in source_value_snapshots.snapshot_reason.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview calculated rows without inserting snapshots.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = create_snapshots(
        snapshot_reason=args.reason,
        dry_run=args.dry_run,
    )
    print_snapshot_summary(rows=rows, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
