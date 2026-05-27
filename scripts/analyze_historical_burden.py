"""Analyze historical operational burden in the local job pipeline database.

This script is intentionally read-only. It does not delete, archive, update or
classify persisted rows. Its purpose is to quantify historical data burden before
windowed source-value trends or cleanup/retention rules are implemented.

Usage:
    python -m scripts.analyze_historical_burden
    python -m scripts.analyze_historical_burden --limit 25
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from src.config import get_database_config


CORE_TABLE_NAMES = [
    "search_profiles",
    "search_terms",
    "ingestion_runs",
    "raw_jobs",
    "job_observations",
    "silver_processing_decisions",
    "silver_jobs",
    "source_value_snapshots",
]


DATABASE_SIZE_SQL = """
SELECT
    c.relname AS table_name,
    pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
    pg_size_pretty(pg_relation_size(c.oid)) AS table_size,
    pg_size_pretty(pg_indexes_size(c.oid)) AS index_size
FROM pg_class c
JOIN pg_namespace n
    ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
  AND c.relname = ANY(%s)
ORDER BY pg_total_relation_size(c.oid) DESC, c.relname;
"""


SOURCE_VOLUME_SQL = """
WITH source_names AS (
    SELECT source_name FROM ingestion_runs
    UNION
    SELECT source_name FROM raw_jobs
    UNION
    SELECT source_name FROM job_observations
    UNION
    SELECT source_name FROM silver_jobs
),
run_base AS (
    SELECT
        source_name,
        COUNT(*) AS ingestion_runs,
        COUNT(*) FILTER (WHERE status = 'success') AS successful_runs,
        COUNT(*) FILTER (WHERE status <> 'success') AS failed_runs,
        COALESCE(SUM(total_loaded), 0) AS total_loaded,
        COALESCE(SUM(inserted_count), 0) AS inserted_count,
        COALESCE(SUM(duplicate_count), 0) AS duplicate_count,
        MIN(started_at) AS first_run_at,
        MAX(started_at) AS latest_run_at
    FROM ingestion_runs
    GROUP BY source_name
),
raw_base AS (
    SELECT
        source_name,
        COUNT(*) AS raw_jobs,
        COUNT(*) FILTER (WHERE external_job_id IS NULL) AS raw_jobs_without_external_id,
        COUNT(*) FILTER (WHERE raw_data ? 'matching') AS raw_jobs_with_matching_metadata,
        COALESCE(SUM(pg_column_size(raw_data)), 0) AS raw_data_bytes,
        MIN(fetched_at) AS first_raw_at,
        MAX(fetched_at) AS latest_raw_at
    FROM raw_jobs
    GROUP BY source_name
),
observation_base AS (
    SELECT
        source_name,
        COUNT(*) AS observations,
        COUNT(DISTINCT ingestion_run_id) AS observation_runs,
        MIN(observed_at) AS first_observed_at,
        MAX(observed_at) AS latest_observed_at
    FROM job_observations
    GROUP BY source_name
),
silver_base AS (
    SELECT
        source_name,
        COUNT(*) AS silver_jobs,
        COUNT(DISTINCT canonical_key_candidate)
            FILTER (WHERE canonical_key_candidate IS NOT NULL) AS distinct_candidate_keys,
        COUNT(DISTINCT normalized_company_name)
            FILTER (WHERE normalized_company_name IS NOT NULL) AS distinct_companies
    FROM silver_jobs
    GROUP BY source_name
)
SELECT
    sn.source_name,
    COALESCE(rb.ingestion_runs, 0) AS ingestion_runs,
    COALESCE(rb.successful_runs, 0) AS successful_runs,
    COALESCE(rb.failed_runs, 0) AS failed_runs,
    COALESCE(rb.total_loaded, 0) AS total_loaded,
    COALESCE(rb.inserted_count, 0) AS inserted_count,
    COALESCE(rb.duplicate_count, 0) AS duplicate_count,
    ROUND(100.0 * COALESCE(rb.duplicate_count, 0) / NULLIF(rb.total_loaded, 0), 2)
        AS run_duplicate_rate_pct,
    COALESCE(raw.raw_jobs, 0) AS raw_jobs,
    COALESCE(raw.raw_jobs_with_matching_metadata, 0) AS raw_jobs_with_matching_metadata,
    COALESCE(raw.raw_jobs_without_external_id, 0) AS raw_jobs_without_external_id,
    pg_size_pretty(COALESCE(raw.raw_data_bytes, 0)::bigint) AS raw_data_size,
    COALESCE(obs.observations, 0) AS observations,
    COALESCE(sb.silver_jobs, 0) AS silver_jobs,
    ROUND(100.0 * COALESCE(sb.silver_jobs, 0) / NULLIF(raw.raw_jobs, 0), 2)
        AS silver_yield_from_raw_pct,
    COALESCE(sb.distinct_companies, 0) AS distinct_companies,
    COALESCE(sb.distinct_candidate_keys, 0) AS distinct_candidate_keys,
    rb.first_run_at,
    rb.latest_run_at,
    raw.first_raw_at,
    raw.latest_raw_at
FROM source_names sn
LEFT JOIN run_base rb
    ON rb.source_name = sn.source_name
LEFT JOIN raw_base raw
    ON raw.source_name = sn.source_name
LEFT JOIN observation_base obs
    ON obs.source_name = sn.source_name
LEFT JOIN silver_base sb
    ON sb.source_name = sn.source_name
ORDER BY
    COALESCE(raw.raw_jobs, 0) DESC,
    COALESCE(rb.total_loaded, 0) DESC,
    sn.source_name;
"""


RUN_TERM_HISTORY_SQL = """
SELECT
    ir.source_name,
    COALESCE(sp.profile_name, '<missing_profile>') AS profile_name,
    COALESCE(ir.search_term, '<multi-term_or_missing>') AS search_term_snapshot,
    COUNT(*) AS runs,
    COUNT(*) FILTER (WHERE ir.status = 'success') AS successful_runs,
    COUNT(*) FILTER (WHERE ir.status <> 'success') AS failed_runs,
    COALESCE(SUM(ir.total_loaded), 0) AS total_loaded,
    COALESCE(SUM(ir.inserted_count), 0) AS inserted_count,
    COALESCE(SUM(ir.duplicate_count), 0) AS duplicate_count,
    ROUND(100.0 * COALESCE(SUM(ir.duplicate_count), 0) / NULLIF(SUM(ir.total_loaded), 0), 2)
        AS duplicate_rate_pct,
    MIN(ir.started_at) AS first_started_at,
    MAX(ir.started_at) AS latest_started_at
FROM ingestion_runs ir
LEFT JOIN search_profiles sp
    ON sp.id = ir.search_profile_id
GROUP BY
    ir.source_name,
    profile_name,
    search_term_snapshot
ORDER BY
    ir.source_name,
    first_started_at,
    search_term_snapshot;
"""


RAW_INITIAL_LINEAGE_SQL = """
SELECT
    rj.source_name,
    COALESCE(sp.profile_name, '<missing_profile>') AS initial_profile_name,
    COALESCE(ir.search_term, '<multi-term_or_missing>') AS initial_search_term_snapshot,
    COUNT(*) AS raw_jobs,
    COUNT(*) FILTER (WHERE rj.raw_data ? 'matching') AS raw_jobs_with_matching_metadata,
    COUNT(*) FILTER (WHERE NOT (rj.raw_data ? 'matching')) AS raw_jobs_without_matching_metadata,
    COUNT(*) FILTER (WHERE spd.decision = 'included') AS included_decisions,
    COUNT(*) FILTER (WHERE spd.decision = 'skipped') AS skipped_decisions,
    COUNT(sj.id) AS silver_jobs,
    pg_size_pretty(COALESCE(SUM(pg_column_size(rj.raw_data)), 0)::bigint) AS raw_data_size,
    MIN(rj.fetched_at) AS first_fetched_at,
    MAX(rj.fetched_at) AS latest_fetched_at
FROM raw_jobs rj
LEFT JOIN ingestion_runs ir
    ON ir.id = rj.ingestion_run_id
LEFT JOIN search_profiles sp
    ON sp.id = rj.search_profile_id
LEFT JOIN silver_processing_decisions spd
    ON spd.raw_job_id = rj.id
LEFT JOIN silver_jobs sj
    ON sj.raw_job_id = rj.id
GROUP BY
    rj.source_name,
    initial_profile_name,
    initial_search_term_snapshot
ORDER BY
    raw_jobs DESC,
    rj.source_name,
    initial_profile_name;
"""


BURDEN_CATEGORY_SQL = """
WITH classified_raw_jobs AS (
    SELECT
        rj.id,
        rj.source_name,
        rj.raw_data,
        rj.fetched_at,
        ir.search_term,
        sp.profile_name,
        CASE
            WHEN rj.ingestion_run_id IS NULL OR rj.search_profile_id IS NULL
                THEN 'missing_lineage'
            WHEN COALESCE(sp.profile_name, '') ILIKE '%%test%%'
                THEN 'possible_test_data'
            WHEN rj.source_name LIKE 'greenhouse:%%' AND ir.search_term = '*'
                THEN 'greenhouse_legacy_wildcard'
            WHEN rj.source_name LIKE 'greenhouse:%%' AND NOT (rj.raw_data ? 'matching')
                THEN 'greenhouse_without_current_matching_metadata'
            WHEN rj.source_name LIKE 'personio:%%' AND NOT (rj.raw_data ? 'matching')
                THEN 'personio_without_current_matching_metadata'
            WHEN rj.source_name = 'stepstone'
                THEN 'commercial_aggregator_history'
            ELSE 'ordinary_operational_history'
        END AS burden_category
    FROM raw_jobs rj
    LEFT JOIN ingestion_runs ir
        ON ir.id = rj.ingestion_run_id
    LEFT JOIN search_profiles sp
        ON sp.id = rj.search_profile_id
)
SELECT
    burden_category,
    source_name,
    COUNT(*) AS raw_jobs,
    pg_size_pretty(COALESCE(SUM(pg_column_size(raw_data)), 0)::bigint) AS raw_data_size,
    MIN(fetched_at) AS first_fetched_at,
    MAX(fetched_at) AS latest_fetched_at
FROM classified_raw_jobs
GROUP BY
    burden_category,
    source_name
ORDER BY
    raw_jobs DESC,
    burden_category,
    source_name;
"""


TOP_RUN_BURDEN_SQL = """
SELECT
    ir.id AS run_id,
    ir.started_at,
    ir.source_name,
    COALESCE(sp.profile_name, '<missing_profile>') AS profile_name,
    COALESCE(ir.search_term, '<multi-term_or_missing>') AS search_term_snapshot,
    ir.status,
    ir.total_loaded,
    ir.inserted_count,
    ir.duplicate_count,
    ROUND(100.0 * ir.duplicate_count / NULLIF(ir.total_loaded, 0), 2)
        AS duplicate_rate_pct,
    CASE
        WHEN ir.search_term = '*'
            THEN 'wildcard_run'
        WHEN ir.source_name LIKE 'greenhouse:%%' AND ir.search_term IS NULL
            THEN 'full_fetch_multi_term_greenhouse'
        WHEN ir.source_name LIKE 'personio:%%' AND ir.search_term IS NULL
            THEN 'full_fetch_multi_term_personio'
        WHEN ir.status <> 'success'
            THEN 'failed_run'
        ELSE 'standard_run'
    END AS run_signal,
    LEFT(COALESCE(ir.requested_url, ''), 120) AS requested_url_preview
FROM ingestion_runs ir
LEFT JOIN search_profiles sp
    ON sp.id = ir.search_profile_id
ORDER BY
    ir.duplicate_count DESC,
    ir.total_loaded DESC,
    ir.started_at DESC
LIMIT %s;
"""


FAILED_RUNS_SQL = """
SELECT
    ir.source_name,
    COALESCE(sp.profile_name, '<missing_profile>') AS profile_name,
    COALESCE(ir.error_type, '<none>') AS error_type,
    COALESCE(ir.error_stage, '<none>') AS error_stage,
    COUNT(*) AS failed_runs,
    MIN(ir.started_at) AS first_failed_at,
    MAX(ir.started_at) AS latest_failed_at,
    LEFT(COALESCE(MAX(ir.error_message), ''), 160) AS example_error_message
FROM ingestion_runs ir
LEFT JOIN search_profiles sp
    ON sp.id = ir.search_profile_id
WHERE ir.status <> 'success'
GROUP BY
    ir.source_name,
    profile_name,
    error_type,
    error_stage
ORDER BY
    failed_runs DESC,
    latest_failed_at DESC;
"""


SOURCE_VALUE_SNAPSHOT_HISTORY_SQL = """
SELECT
    source_name,
    source_family,
    COALESCE(source_target, '<none>') AS source_target,
    snapshot_reason,
    COUNT(*) AS snapshots,
    MIN(snapshot_at) AS first_snapshot_at,
    MAX(snapshot_at) AS latest_snapshot_at,
    MAX(raw_jobs) AS max_raw_jobs,
    MAX(silver_jobs) AS max_silver_jobs,
    MAX(duplicate_rate_pct) AS max_duplicate_rate_pct,
    MAX(failure_rate_pct) AS max_failure_rate_pct
FROM source_value_snapshots
GROUP BY
    source_name,
    source_family,
    source_target,
    snapshot_reason
ORDER BY
    source_family,
    source_name,
    snapshot_reason;
"""


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


def fetch_rows(
    connection: psycopg.Connection,
    sql: str,
    params: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(sql, params)
        return list(cursor.fetchall())


def fetch_database_size_rows(connection: psycopg.Connection) -> list[dict[str, Any]]:
    """Fetch core table sizes with exact row counts.

    PostgreSQL statistics such as pg_stat_user_tables.n_live_tup are estimates and
    can be stale in small local databases. Historical burden analysis should not
    present those estimates as row counts, so this function uses COUNT(*) for the
    small set of core project tables.
    """

    rows = fetch_rows(
        connection,
        DATABASE_SIZE_SQL,
        (CORE_TABLE_NAMES,),
    )

    for row in rows:
        table_name = row["table_name"]
        count_query = sql.SQL("SELECT COUNT(*) FROM {};").format(
            sql.Identifier(table_name)
        )
        with connection.cursor() as cursor:
            cursor.execute(count_query)
            row["actual_rows"] = cursor.fetchone()[0]

    return rows


def table_exists(connection: psycopg.Connection, table_name: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s);", (f"public.{table_name}",))
        return cursor.fetchone()[0] is not None


def rows_to_table(rows: list[dict[str, Any]]) -> tuple[list[str], list[list[Any]]]:
    if not rows:
        return [], []

    headers = list(rows[0].keys())
    table_rows = [[row[header] for header in headers] for row in rows]
    return headers, table_rows


def print_section(title: str, rows: list[dict[str, Any]]) -> None:
    print()
    print(f"=== {title} ===")
    print()

    headers, table_rows = rows_to_table(rows)
    if not headers:
        print("No rows.")
        return

    print_table(headers=headers, rows=table_rows)


def run_analysis(limit: int) -> None:
    config = get_database_config()

    with psycopg.connect(**config) as connection:
        database_size_rows = fetch_database_size_rows(connection)
        source_volume_rows = fetch_rows(connection, SOURCE_VOLUME_SQL)
        run_term_history_rows = fetch_rows(connection, RUN_TERM_HISTORY_SQL)
        raw_initial_lineage_rows = fetch_rows(connection, RAW_INITIAL_LINEAGE_SQL)
        burden_category_rows = fetch_rows(connection, BURDEN_CATEGORY_SQL)
        top_run_burden_rows = fetch_rows(connection, TOP_RUN_BURDEN_SQL, (limit,))
        failed_run_rows = fetch_rows(connection, FAILED_RUNS_SQL)

        if table_exists(connection, "source_value_snapshots"):
            snapshot_history_rows = fetch_rows(connection, SOURCE_VALUE_SNAPSHOT_HISTORY_SQL)
        else:
            snapshot_history_rows = []

    print()
    print("Historical Burden Analysis")
    print("Mode: read-only")
    print("Cleanup action: none")

    print_section("Database Size by Core Table", database_size_rows)
    print_section("Historical Volume by Source", source_volume_rows)
    print_section("Run History by Source/Profile/Search-Term Snapshot", run_term_history_rows)
    print_section("Raw Job Initial Lineage", raw_initial_lineage_rows)
    print_section("Initial Burden Categories", burden_category_rows)
    print_section("Top Ingestion Runs by Duplicate/Volume Burden", top_run_burden_rows)
    print_section("Failed Run Burden", failed_run_rows)

    if snapshot_history_rows:
        print_section("Source Value Snapshot History", snapshot_history_rows)

    print()
    print("Interpretation boundary:")
    print("- This script identifies candidates for review, not rows to delete.")
    print("- Categories are intentionally conservative and may be refined after reviewing the output.")
    print("- Windowed trends should wait until historical burden is understood.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of high-burden ingestion runs to show.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_analysis(limit=args.limit)


if __name__ == "__main__":
    main()
