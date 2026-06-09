#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.market_sensor_controlled_activation import (
    BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
    BA_SOURCE_NAME,
    MarketSensorProfileState,
    MarketSensorTermState,
)
from src.search_intelligence.sensor001h_ba_remote_post_activation_monitoring import (
    build_sensor001h_post_activation_monitoring,
    render_markdown,
)

DEFAULT_DOCKER_CONTAINER = "job_pipeline_postgres"
DEFAULT_DOCKER_USER = "job_user"
DEFAULT_DOCKER_DB = "job_pipeline"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build SENSOR-001H BA remote/nationwide post-activation monitoring report without ingestion or DB writes."
    )
    parser.add_argument("--sensor001g-json", default=None, help="Path to a SENSOR-001G JSON export. Defaults to latest exports/sensor001g_*.json.")
    parser.add_argument("--dsn", default=None, help="Optional PostgreSQL DSN. Defaults to JOB_PIPELINE_DATABASE_URL / DATABASE_URL.")
    parser.add_argument("--source-name", default=BA_SOURCE_NAME)
    parser.add_argument("--output-dir", default="exports")
    parser.add_argument("--docker-container", default=DEFAULT_DOCKER_CONTAINER)
    parser.add_argument("--docker-user", default=DEFAULT_DOCKER_USER)
    parser.add_argument("--docker-db", default=DEFAULT_DOCKER_DB)
    parser.add_argument("--no-docker-fallback", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"sensor001h_ba_remote_post_activation_monitoring_{stamp}.json"
    md_path = output_dir / f"sensor001h_ba_remote_post_activation_monitoring_{stamp}.md"

    try:
        sensor001g_path = Path(args.sensor001g_json) if args.sensor001g_json else latest_sensor001g_report_path(output_dir)
        sensor001g_report = json.loads(sensor001g_path.read_text(encoding="utf-8"))
        profiles, terms, term_rows, latest_run_rows, duplicate_provenance_rows, access = load_state(args)
        report_obj = build_sensor001h_post_activation_monitoring(
            sensor001g_report=sensor001g_report,
            profiles=profiles,
            terms=terms,
            term_observation_rows=term_rows,
            latest_run_rows=latest_run_rows,
            duplicate_provenance_rows=duplicate_provenance_rows,
        )
        report = report_obj.as_dict()
        report["sensor001g_input_path"] = str(sensor001g_path)
        report["db_access_method"] = access
        exit_code = 0 if report.get("overall_status") in {
            "monitoring_ready_awaiting_first_run",
            "monitoring_ready_with_observed_runs",
            "monitoring_attention_required_failed_runs",
            "monitoring_attention_required_duplicate_dominated",
        } else 1
    except Exception as error:
        report = build_failure_report(args.source_name, error)
        exit_code = 2

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print("# SENSOR-001H BA Remote/Nationwide Post-Activation Monitoring")
    print(f"overall_status={report.get('overall_status')}")
    if report.get("db_access_method"):
        print(f"db_access_method={report['db_access_method']}")
    summary = report.get("metric_summary", {})
    if summary:
        print(f"ingestion_run_count={summary.get('ingestion_run_count')}")
        print(f"total_loaded={summary.get('total_loaded')}")
        print(f"inserted_count={summary.get('inserted_count')}")
        print(f"duplicate_count={summary.get('duplicate_count')}")
        print(f"failed_run_count={summary.get('failed_run_count')}")
    if report.get("database_error"):
        error = report["database_error"]
        print(f"database_error={error['type']}: {error['message']}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    return exit_code


def load_state(
    args: argparse.Namespace,
) -> tuple[
    tuple[MarketSensorProfileState, ...],
    tuple[MarketSensorTermState, ...],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    str,
]:
    dsn = resolve_dsn(args.dsn)
    if dsn:
        profiles, terms, term_rows, latest_run_rows, duplicate_provenance_rows = load_state_with_psycopg(dsn, args.source_name)
        return profiles, terms, term_rows, latest_run_rows, duplicate_provenance_rows, "psycopg_dsn"
    if args.no_docker_fallback:
        raise RuntimeError("No DSN configured and docker fallback disabled.")
    profiles, terms, term_rows, latest_run_rows, duplicate_provenance_rows = load_state_with_docker_psql(args)
    return profiles, terms, term_rows, latest_run_rows, duplicate_provenance_rows, "docker_exec_psql"


def load_state_with_psycopg(
    dsn: str,
    source_name: str,
) -> tuple[tuple[MarketSensorProfileState, ...], tuple[MarketSensorTermState, ...], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    import psycopg

    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            with conn.cursor() as cursor:
                cursor.execute(PROFILES_SQL, {"source_name": source_name})
                profile_rows = cursor.fetchall()
                profile_columns = [desc.name for desc in cursor.description]
                profiles = tuple(MarketSensorProfileState.from_mapping(dict(zip(profile_columns, row))) for row in profile_rows)

                cursor.execute(TERMS_SQL, {"source_name": source_name})
                term_db_rows = cursor.fetchall()
                term_columns = [desc.name for desc in cursor.description]
                terms = tuple(MarketSensorTermState.from_mapping(dict(zip(term_columns, row))) for row in term_db_rows)

                cursor.execute(TERM_OBSERVATIONS_SQL, {"profile_name": BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME, "source_name": source_name})
                observation_rows = cursor.fetchall()
                observation_columns = [desc.name for desc in cursor.description]
                term_observations = [dict(zip(observation_columns, row)) for row in observation_rows]

                cursor.execute(LATEST_RUNS_SQL, {"profile_name": BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME, "source_name": source_name})
                latest_rows = cursor.fetchall()
                latest_columns = [desc.name for desc in cursor.description]
                latest_runs = [dict(zip(latest_columns, row)) for row in latest_rows]

                cursor.execute(DUPLICATE_PROVENANCE_SQL, {"profile_name": BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME, "source_name": source_name})
                duplicate_rows = cursor.fetchall()
                duplicate_columns = [desc.name for desc in cursor.description]
                duplicate_provenance = [dict(zip(duplicate_columns, row)) for row in duplicate_rows]
    return profiles, terms, term_observations, latest_runs, duplicate_provenance


def load_state_with_docker_psql(
    args: argparse.Namespace,
) -> tuple[tuple[MarketSensorProfileState, ...], tuple[MarketSensorTermState, ...], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    profile_rows = run_docker_json_query(wrap_json_query(PROFILES_SQL_DOCKER.replace("__SOURCE_NAME__", sql_literal(args.source_name))), args)
    term_rows = run_docker_json_query(wrap_json_query(TERMS_SQL_DOCKER.replace("__SOURCE_NAME__", sql_literal(args.source_name))), args)
    observation_rows = run_docker_json_query(
        wrap_json_query(
            TERM_OBSERVATIONS_SQL_DOCKER
            .replace("__PROFILE_NAME__", sql_literal(BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME))
            .replace("__SOURCE_NAME__", sql_literal(args.source_name))
        ),
        args,
    )
    latest_run_rows = run_docker_json_query(
        wrap_json_query(
            LATEST_RUNS_SQL_DOCKER
            .replace("__PROFILE_NAME__", sql_literal(BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME))
            .replace("__SOURCE_NAME__", sql_literal(args.source_name))
        ),
        args,
    )
    duplicate_provenance_rows = run_docker_json_query(
        wrap_json_query(
            DUPLICATE_PROVENANCE_SQL_DOCKER
            .replace("__PROFILE_NAME__", sql_literal(BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME))
            .replace("__SOURCE_NAME__", sql_literal(args.source_name))
        ),
        args,
    )
    return (
        tuple(MarketSensorProfileState.from_mapping(row) for row in profile_rows),
        tuple(MarketSensorTermState.from_mapping(row) for row in term_rows),
        observation_rows,
        latest_run_rows,
        duplicate_provenance_rows,
    )


def run_docker_json_query(sql: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    command = [
        "docker", "exec", "-i", args.docker_container,
        "psql", "-U", args.docker_user, "-d", args.docker_db,
        "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", sql,
    ]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "docker psql query failed")
    payload = result.stdout.strip()
    return [] if not payload else json.loads(payload)


def latest_sensor001g_report_path(output_dir: Path) -> Path:
    matches = sorted(output_dir.glob("sensor001g_ba_remote_controlled_activation_gate_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError("No SENSOR-001G JSON export found. Pass --sensor001g-json explicitly.")
    return matches[0]


def wrap_json_query(inner_sql: str) -> str:
    return f"select coalesce(json_agg(row_to_json(rows)), '[]'::json) from ({inner_sql}) rows;"


def resolve_dsn(explicit_dsn: str | None) -> str | None:
    return explicit_dsn or os.getenv("JOB_PIPELINE_DATABASE_URL") or os.getenv("DATABASE_URL")


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_failure_report(source_name: str, error: BaseException) -> dict[str, Any]:
    return {
        "schema_version": "sensor001h.ba_remote_post_activation_monitoring.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "work_item": "SENSOR-001H BA Remote/Nationwide Post-Activation Monitoring",
        "source_name": source_name,
        "overall_status": "monitoring_failed",
        "database_error": {"type": type(error).__name__, "message": str(error).splitlines()[0] if str(error) else "unknown error"},
        "findings": [],
        "next_action": "Inspect the failure and rerun after repair.",
        "safety_boundary": {
            "read_only_monitoring": True,
            "external_requests": False,
            "database_reads": False,
            "database_writes": False,
            "raw_jobs_write": False,
            "ingestion_run_write": False,
            "scheduler_mutation": False,
            "candidate_or_gate_mutation": False,
            "connector_activation": False,
            "bronze_silver_gold_mutation": False,
        },
    }


PROFILES_SQL = """
SELECT id, profile_name, source_name, search_term, search_location, search_radius_km, offer_type, page_size, is_active
FROM search_profiles
WHERE source_name = %(source_name)s
ORDER BY profile_name;
"""

TERMS_SQL = """
SELECT sp.profile_name, st.search_term, st.is_active
FROM search_profiles sp
JOIN search_terms st ON st.search_profile_id = sp.id
WHERE sp.source_name = %(source_name)s
ORDER BY sp.profile_name, st.search_term;
"""

TERM_OBSERVATIONS_SQL = """
WITH run_metrics AS (
    SELECT
        st.id AS search_term_id,
        st.search_term,
        COUNT(ir.id)::int AS ingestion_run_count,
        COALESCE(SUM(ir.total_loaded), 0)::int AS total_loaded,
        COALESCE(SUM(ir.inserted_count), 0)::int AS inserted_count,
        COALESCE(SUM(ir.duplicate_count), 0)::int AS duplicate_count,
        COALESCE(SUM(CASE WHEN ir.status = 'failed' THEN 1 ELSE 0 END), 0)::int AS failed_run_count,
        MAX(ir.started_at)::text AS latest_started_at
    FROM search_profiles sp
    JOIN search_terms st ON st.search_profile_id = sp.id AND st.is_active = TRUE
    LEFT JOIN ingestion_runs ir
      ON ir.search_profile_id = sp.id
     AND (ir.search_term = st.search_term OR ir.search_term_id = st.id)
    WHERE sp.profile_name = %(profile_name)s
      AND sp.source_name = %(source_name)s
    GROUP BY st.id, st.search_term
),
raw_job_counts AS (
    SELECT
        st.id AS search_term_id,
        COUNT(r.id)::int AS raw_jobs_count
    FROM search_profiles sp
    JOIN search_terms st ON st.search_profile_id = sp.id AND st.is_active = TRUE
    LEFT JOIN ingestion_runs ir
      ON ir.search_profile_id = sp.id
     AND (ir.search_term = st.search_term OR ir.search_term_id = st.id)
    LEFT JOIN raw_jobs r ON r.ingestion_run_id = ir.id
    WHERE sp.profile_name = %(profile_name)s
      AND sp.source_name = %(source_name)s
    GROUP BY st.id
)
SELECT
    rm.search_term,
    rm.ingestion_run_count,
    COALESCE(rjc.raw_jobs_count, 0)::int AS raw_jobs_count,
    rm.total_loaded,
    rm.inserted_count,
    rm.duplicate_count,
    rm.failed_run_count,
    rm.latest_started_at
FROM run_metrics rm
LEFT JOIN raw_job_counts rjc ON rjc.search_term_id = rm.search_term_id
ORDER BY rm.search_term;
"""

LATEST_RUNS_SQL = """
SELECT
    ir.id,
    ir.status,
    ir.search_term,
    ir.total_loaded,
    ir.inserted_count,
    ir.duplicate_count,
    ir.error_type,
    ir.error_stage,
    ir.error_message,
    ir.started_at::text AS started_at,
    ir.finished_at::text AS finished_at
FROM ingestion_runs ir
JOIN search_profiles sp ON sp.id = ir.search_profile_id
WHERE sp.profile_name = %(profile_name)s
  AND sp.source_name = %(source_name)s
ORDER BY ir.started_at DESC
LIMIT 10;
"""

PROFILES_SQL_DOCKER = """
SELECT id, profile_name, source_name, search_term, search_location, search_radius_km, offer_type, page_size, is_active
FROM search_profiles
WHERE source_name = __SOURCE_NAME__
ORDER BY profile_name
"""

TERMS_SQL_DOCKER = """
SELECT sp.profile_name, st.search_term, st.is_active
FROM search_profiles sp
JOIN search_terms st ON st.search_profile_id = sp.id
WHERE sp.source_name = __SOURCE_NAME__
ORDER BY sp.profile_name, st.search_term
"""

TERM_OBSERVATIONS_SQL_DOCKER = """
WITH run_metrics AS (
    SELECT
        st.id AS search_term_id,
        st.search_term,
        COUNT(ir.id)::int AS ingestion_run_count,
        COALESCE(SUM(ir.total_loaded), 0)::int AS total_loaded,
        COALESCE(SUM(ir.inserted_count), 0)::int AS inserted_count,
        COALESCE(SUM(ir.duplicate_count), 0)::int AS duplicate_count,
        COALESCE(SUM(CASE WHEN ir.status = 'failed' THEN 1 ELSE 0 END), 0)::int AS failed_run_count,
        MAX(ir.started_at)::text AS latest_started_at
    FROM search_profiles sp
    JOIN search_terms st ON st.search_profile_id = sp.id AND st.is_active = TRUE
    LEFT JOIN ingestion_runs ir
      ON ir.search_profile_id = sp.id
     AND (ir.search_term = st.search_term OR ir.search_term_id = st.id)
    WHERE sp.profile_name = __PROFILE_NAME__
      AND sp.source_name = __SOURCE_NAME__
    GROUP BY st.id, st.search_term
),
raw_job_counts AS (
    SELECT
        st.id AS search_term_id,
        COUNT(r.id)::int AS raw_jobs_count
    FROM search_profiles sp
    JOIN search_terms st ON st.search_profile_id = sp.id AND st.is_active = TRUE
    LEFT JOIN ingestion_runs ir
      ON ir.search_profile_id = sp.id
     AND (ir.search_term = st.search_term OR ir.search_term_id = st.id)
    LEFT JOIN raw_jobs r ON r.ingestion_run_id = ir.id
    WHERE sp.profile_name = __PROFILE_NAME__
      AND sp.source_name = __SOURCE_NAME__
    GROUP BY st.id
)
SELECT
    rm.search_term,
    rm.ingestion_run_count,
    COALESCE(rjc.raw_jobs_count, 0)::int AS raw_jobs_count,
    rm.total_loaded,
    rm.inserted_count,
    rm.duplicate_count,
    rm.failed_run_count,
    rm.latest_started_at
FROM run_metrics rm
LEFT JOIN raw_job_counts rjc ON rjc.search_term_id = rm.search_term_id
ORDER BY rm.search_term
"""

LATEST_RUNS_SQL_DOCKER = """
SELECT
    ir.id,
    ir.status,
    ir.search_term,
    ir.total_loaded,
    ir.inserted_count,
    ir.duplicate_count,
    ir.error_type,
    ir.error_stage,
    ir.error_message,
    ir.started_at::text AS started_at,
    ir.finished_at::text AS finished_at
FROM ingestion_runs ir
JOIN search_profiles sp ON sp.id = ir.search_profile_id
WHERE sp.profile_name = __PROFILE_NAME__
  AND sp.source_name = __SOURCE_NAME__
ORDER BY ir.started_at DESC
LIMIT 10
"""


DUPLICATE_PROVENANCE_SQL = """
WITH remote_profile AS (
    SELECT id, profile_name, source_name
    FROM search_profiles
    WHERE profile_name = %(profile_name)s
      AND source_name = %(source_name)s
),
latest_remote_runs AS (
    SELECT ir.*
    FROM ingestion_runs ir
    JOIN remote_profile rp ON rp.id = ir.search_profile_id
    ORDER BY ir.started_at DESC
    LIMIT 7
),
duplicate_observations AS (
    SELECT
        current_run.id AS duplicate_run_id,
        current_run.search_term AS duplicate_seen_in_term,
        jo.external_job_id,
        jo.raw_job_id AS existing_raw_job_id,
        original_raw.ingestion_run_id AS original_run_id,
        original_run.search_term AS original_search_term,
        original_profile.profile_name AS original_profile_name,
        original_profile.source_name AS original_source_name,
        COALESCE(
            original_raw.raw_data #>> '{result_card,title}',
            original_raw.raw_data #>> '{job,titel}',
            original_raw.raw_data #>> '{job,title}',
            '<missing>'
        ) AS title,
        COALESCE(
            original_raw.raw_data #>> '{result_card,company_name}',
            original_raw.raw_data #>> '{job,arbeitgeber}',
            original_raw.raw_data #>> '{job,company_name}',
            original_raw.raw_data #>> '{job,company}',
            '<missing>'
        ) AS company_name,
        original_raw.source_url
    FROM latest_remote_runs current_run
    JOIN job_observations jo
      ON jo.ingestion_run_id = current_run.id
    JOIN raw_jobs original_raw
      ON original_raw.source_name = current_run.source_name
     AND original_raw.external_job_id = jo.external_job_id
    LEFT JOIN ingestion_runs original_run
      ON original_run.id = original_raw.ingestion_run_id
    LEFT JOIN search_profiles original_profile
      ON original_profile.id = original_raw.search_profile_id
    WHERE jo.external_job_id IS NOT NULL
      AND original_raw.ingestion_run_id IS DISTINCT FROM current_run.id
)
SELECT
    *,
    CASE
        WHEN original_run_id IN (SELECT id FROM latest_remote_runs)
            THEN 'cross_term_overlap_within_current_remote_run'
        WHEN original_profile_name = %(profile_name)s
            THEN 'previous_same_remote_profile_run'
        WHEN original_source_name = %(source_name)s
            THEN 'previous_ba_profile_or_older_ba_run'
        ELSE 'other_or_unknown'
    END AS provenance_class
FROM duplicate_observations
ORDER BY duplicate_run_id, external_job_id;
"""

DUPLICATE_PROVENANCE_SQL_DOCKER = """
WITH remote_profile AS (
    SELECT id, profile_name, source_name
    FROM search_profiles
    WHERE profile_name = __PROFILE_NAME__
      AND source_name = __SOURCE_NAME__
),
latest_remote_runs AS (
    SELECT ir.*
    FROM ingestion_runs ir
    JOIN remote_profile rp ON rp.id = ir.search_profile_id
    ORDER BY ir.started_at DESC
    LIMIT 7
),
duplicate_observations AS (
    SELECT
        current_run.id AS duplicate_run_id,
        current_run.search_term AS duplicate_seen_in_term,
        jo.external_job_id,
        jo.raw_job_id AS existing_raw_job_id,
        original_raw.ingestion_run_id AS original_run_id,
        original_run.search_term AS original_search_term,
        original_profile.profile_name AS original_profile_name,
        original_profile.source_name AS original_source_name,
        COALESCE(
            original_raw.raw_data #>> '{result_card,title}',
            original_raw.raw_data #>> '{job,titel}',
            original_raw.raw_data #>> '{job,title}',
            '<missing>'
        ) AS title,
        COALESCE(
            original_raw.raw_data #>> '{result_card,company_name}',
            original_raw.raw_data #>> '{job,arbeitgeber}',
            original_raw.raw_data #>> '{job,company_name}',
            original_raw.raw_data #>> '{job,company}',
            '<missing>'
        ) AS company_name,
        original_raw.source_url
    FROM latest_remote_runs current_run
    JOIN job_observations jo
      ON jo.ingestion_run_id = current_run.id
    JOIN raw_jobs original_raw
      ON original_raw.source_name = current_run.source_name
     AND original_raw.external_job_id = jo.external_job_id
    LEFT JOIN ingestion_runs original_run
      ON original_run.id = original_raw.ingestion_run_id
    LEFT JOIN search_profiles original_profile
      ON original_profile.id = original_raw.search_profile_id
    WHERE jo.external_job_id IS NOT NULL
      AND original_raw.ingestion_run_id IS DISTINCT FROM current_run.id
)
SELECT
    *,
    CASE
        WHEN original_run_id IN (SELECT id FROM latest_remote_runs)
            THEN 'cross_term_overlap_within_current_remote_run'
        WHEN original_profile_name = __PROFILE_NAME__
            THEN 'previous_same_remote_profile_run'
        WHEN original_source_name = __SOURCE_NAME__
            THEN 'previous_ba_profile_or_older_ba_run'
        ELSE 'other_or_unknown'
    END AS provenance_class
FROM duplicate_observations
ORDER BY duplicate_run_id, external_job_id
"""

if __name__ == "__main__":
    raise SystemExit(main())
