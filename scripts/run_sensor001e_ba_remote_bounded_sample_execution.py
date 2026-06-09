#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.connectors.registry import create_connector
from src.search_intelligence.market_sensor_controlled_activation import (
    BA_SOURCE_NAME,
    MarketSensorProfileState,
    MarketSensorTermState,
)
from src.search_intelligence.sensor001e_ba_remote_bounded_sample_execution import (
    build_sensor001e_bounded_sample_execution,
    render_markdown,
)

DEFAULT_DOCKER_CONTAINER = "job_pipeline_postgres"
DEFAULT_DOCKER_USER = "job_user"
DEFAULT_DOCKER_DB = "job_pipeline"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute SENSOR-001E bounded BA remote/nationwide external sample without Bronze/Silver/Gold writes."
    )
    parser.add_argument("--execute-approved", action="store_true", help="Required to perform external BA requests after explicit operator approval.")
    parser.add_argument("--dsn", default=None, help="Optional PostgreSQL DSN. Defaults to JOB_PIPELINE_DATABASE_URL / DATABASE_URL.")
    parser.add_argument("--source-name", default=BA_SOURCE_NAME, help="Source name to inspect. SENSOR-001E currently supports BA only.")
    parser.add_argument("--max-terms", type=int, default=2, help="Maximum review-profile terms to sample.")
    parser.add_argument("--output-dir", default="exports", help="Directory for JSON/Markdown sample artifacts.")
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
    json_path = output_dir / f"sensor001e_ba_remote_bounded_sample_execution_{stamp}.json"
    md_path = output_dir / f"sensor001e_ba_remote_bounded_sample_execution_{stamp}.md"

    try:
        profiles, terms, known_company_keys, access = load_state(args)
        connector = create_connector(args.source_name)
        lookup = ExistingRawJobLookup(args=args)
        report_obj = build_sensor001e_bounded_sample_execution(
            profiles=profiles,
            terms=terms,
            connector=connector,
            existing_raw_job_lookup=lookup,
            known_company_keys=known_company_keys,
            max_terms=args.max_terms,
            execute_approved=args.execute_approved,
        )
        report = report_obj.as_dict()
        report["db_access_method"] = access
        exit_code = 0 if report["overall_status"] in {"approval_required", "sample_executed"} else 1
    except Exception as error:
        report = build_failure_report(args.source_name, error)
        exit_code = 2

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print("# SENSOR-001E BA Remote/Nationwide Bounded Sample Execution Review")
    print(f"overall_status={report.get('overall_status')}")
    print(f"source_name={report.get('source_name')}")
    if report.get("db_access_method"):
        print(f"db_access_method={report['db_access_method']}")
    metrics = report.get("metrics", {})
    if metrics:
        print(f"total_loaded_by_term={metrics.get('total_loaded_by_term')}")
        print(f"inserted_count_by_term={metrics.get('inserted_count_by_term')}")
        print(f"duplicate_count_by_term={metrics.get('duplicate_count_by_term')}")
        print(f"distinct_company_count={metrics.get('distinct_company_count')}")
        print(f"new_company_count={metrics.get('new_company_count')}")
        print(f"error_count={metrics.get('error_count')}")
    if report.get("database_error"):
        error = report["database_error"]
        print(f"database_error={error['type']}: {error['message']}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    return exit_code


class ExistingRawJobLookup:
    def __init__(self, *, args: argparse.Namespace) -> None:
        self.args = args
        self._cache: dict[tuple[str, str | None], bool] = {}

    def __call__(self, *, source_name: str, external_job_id: str | None) -> bool:
        if external_job_id is None:
            return False
        key = (source_name, external_job_id)
        if key not in self._cache:
            self._cache[key] = raw_job_exists(self.args, source_name, external_job_id)
        return self._cache[key]


def load_state(args: argparse.Namespace) -> tuple[tuple[MarketSensorProfileState, ...], tuple[MarketSensorTermState, ...], set[str], str]:
    dsn = resolve_dsn(args.dsn)
    if dsn:
        return (*load_state_with_psycopg(dsn, args.source_name), "psycopg_dsn")
    if args.no_docker_fallback:
        raise RuntimeError("No DSN configured and docker fallback disabled.")
    profiles, terms, known_company_keys = load_state_with_docker_psql(args)
    return profiles, terms, known_company_keys, "docker_exec_psql"


def load_state_with_psycopg(
    dsn: str,
    source_name: str,
) -> tuple[tuple[MarketSensorProfileState, ...], tuple[MarketSensorTermState, ...], set[str]]:
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
                term_rows = cursor.fetchall()
                term_columns = [desc.name for desc in cursor.description]
                terms = tuple(MarketSensorTermState.from_mapping(dict(zip(term_columns, row))) for row in term_rows)

                cursor.execute(KNOWN_COMPANY_KEYS_SQL)
                known_company_keys = {str(row[0]) for row in cursor.fetchall() if row and row[0]}
    return profiles, terms, known_company_keys


def load_state_with_docker_psql(
    args: argparse.Namespace,
) -> tuple[tuple[MarketSensorProfileState, ...], tuple[MarketSensorTermState, ...], set[str]]:
    profile_rows = run_docker_json_query(wrap_json_query(PROFILES_SQL_DOCKER.replace("__SOURCE_NAME__", sql_literal(args.source_name))), args)
    term_rows = run_docker_json_query(wrap_json_query(TERMS_SQL_DOCKER.replace("__SOURCE_NAME__", sql_literal(args.source_name))), args)
    key_rows = run_docker_json_query(wrap_json_query(KNOWN_COMPANY_KEYS_SQL_DOCKER), args)
    return (
        tuple(MarketSensorProfileState.from_mapping(row) for row in profile_rows),
        tuple(MarketSensorTermState.from_mapping(row) for row in term_rows),
        {str(row["company_key"]) for row in key_rows if row.get("company_key")},
    )


def raw_job_exists(args: argparse.Namespace, source_name: str, external_job_id: str) -> bool:
    dsn = resolve_dsn(args.dsn)
    if dsn:
        import psycopg

        with psycopg.connect(dsn) as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                with conn.cursor() as cursor:
                    cursor.execute(RAW_JOB_EXISTS_SQL, {"source_name": source_name, "external_job_id": external_job_id})
                    return bool(cursor.fetchone()[0])

    if args.no_docker_fallback:
        raise RuntimeError("No DSN configured and docker fallback disabled.")

    rows = run_docker_json_query(
        wrap_json_query(
            RAW_JOB_EXISTS_SQL_DOCKER
            .replace("__SOURCE_NAME__", sql_literal(source_name))
            .replace("__EXTERNAL_JOB_ID__", sql_literal(external_job_id))
        ),
        args,
    )
    return bool(rows and rows[0].get("exists"))


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


def wrap_json_query(inner_sql: str) -> str:
    return f"select coalesce(json_agg(row_to_json(rows)), '[]'::json) from ({inner_sql}) rows;"


def resolve_dsn(explicit_dsn: str | None) -> str | None:
    return explicit_dsn or os.getenv("JOB_PIPELINE_DATABASE_URL") or os.getenv("DATABASE_URL")


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_failure_report(source_name: str, error: BaseException) -> dict[str, Any]:
    return {
        "schema_version": "sensor001e.ba_remote_nationwide_bounded_sample_execution.v1",
        "generated_at_utc": datetime.now().astimezone().isoformat(),
        "work_item": "SENSOR-001E BA Remote/Nationwide Bounded Sample Execution Review",
        "source_name": source_name,
        "overall_status": "execution_failed_before_sample",
        "database_error": {"type": type(error).__name__, "message": str(error).splitlines()[0] if str(error) else "unknown error"},
        "safety_boundary": {
            "external_requests": False,
            "database_writes": False,
            "raw_jobs_write": False,
            "ingestion_run_write": False,
            "scheduler_mutation": False,
            "productive_activation": False,
        },
        "findings": [],
        "next_action": "Inspect the failure and rerun after repair.",
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

KNOWN_COMPANY_KEYS_SQL = """
SELECT DISTINCT company_key
FROM employer_origin_source_candidates
WHERE company_key IS NOT NULL
ORDER BY company_key;
"""

RAW_JOB_EXISTS_SQL = """
SELECT EXISTS (
    SELECT 1 FROM raw_jobs
    WHERE source_name = %(source_name)s
      AND external_job_id = %(external_job_id)s
) AS exists;
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

KNOWN_COMPANY_KEYS_SQL_DOCKER = """
SELECT DISTINCT company_key
FROM employer_origin_source_candidates
WHERE company_key IS NOT NULL
ORDER BY company_key
"""

RAW_JOB_EXISTS_SQL_DOCKER = """
SELECT EXISTS (
    SELECT 1 FROM raw_jobs
    WHERE source_name = __SOURCE_NAME__
      AND external_job_id = __EXTERNAL_JOB_ID__
) AS exists
"""


if __name__ == "__main__":
    raise SystemExit(main())
