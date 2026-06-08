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

import psycopg

from src.search_intelligence.market_sensor_controlled_activation import (
    BA_SOURCE_NAME,
    MarketSensorProfileState,
    MarketSensorTermState,
    build_ba_remote_controlled_activation_review,
    render_markdown,
)

DEFAULT_DOCKER_CONTAINER = "job_pipeline_postgres"
DEFAULT_DOCKER_USER = "job_user"
DEFAULT_DOCKER_DB = "job_pipeline"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review SENSOR-001C BA remote/nationwide controlled activation state."
    )
    parser.add_argument("--dsn", default=None, help="Optional PostgreSQL DSN. Defaults to JOB_PIPELINE_DATABASE_URL / DATABASE_URL.")
    parser.add_argument("--source-name", default=BA_SOURCE_NAME, help="Source name to inspect. SENSOR-001C currently supports BA only.")
    parser.add_argument("--output-dir", default="exports", help="Directory for JSON/Markdown review artifacts.")
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
    json_path = output_dir / f"sensor001c_ba_remote_controlled_activation_review_{stamp}.json"
    md_path = output_dir / f"sensor001c_ba_remote_controlled_activation_review_{stamp}.md"

    if args.source_name != BA_SOURCE_NAME:
        report = build_unsupported_source_report(args.source_name)
        exit_code = 1
    else:
        try:
            profiles, terms, access_method = load_state(args)
            review = build_ba_remote_controlled_activation_review(profiles, terms)
            report = review.as_dict()
            report["db_access_method"] = access_method
            exit_code = 0 if report["overall_status"] in {"migration_pending", "review_profile_ready"} else 1
        except Exception as error:
            report = build_database_unavailable_report(args.source_name, error)
            exit_code = 2

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print("# SENSOR-001C BA Remote/Nationwide Controlled Activation Review")
    print(f"overall_status={report.get('overall_status')}")
    print(f"source_name={report.get('source_name')}")
    if report.get("db_access_method"):
        print(f"db_access_method={report['db_access_method']}")
    if report.get("database_error"):
        error = report["database_error"]
        print(f"database_error={error['type']}: {error['message']}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    return exit_code


def load_state(args: argparse.Namespace) -> tuple[tuple[MarketSensorProfileState, ...], tuple[MarketSensorTermState, ...], str]:
    dsn = resolve_dsn(args.dsn)
    if dsn:
        profiles, terms = load_state_with_psycopg(dsn, args.source_name)
        return profiles, terms, "psycopg_dsn"

    if args.no_docker_fallback:
        raise RuntimeError("No DSN configured and docker fallback disabled.")

    profiles, terms = load_state_with_docker_psql(args)
    return profiles, terms, "docker_exec_psql"


def load_state_with_psycopg(
    dsn: str,
    source_name: str,
) -> tuple[tuple[MarketSensorProfileState, ...], tuple[MarketSensorTermState, ...]]:
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

    return profiles, terms


def load_state_with_docker_psql(
    args: argparse.Namespace,
) -> tuple[tuple[MarketSensorProfileState, ...], tuple[MarketSensorTermState, ...]]:
    profile_rows = run_docker_json_query(
        wrap_json_query(PROFILES_SQL_DOCKER.replace("__SOURCE_NAME__", sql_literal(args.source_name))),
        args,
    )
    term_rows = run_docker_json_query(
        wrap_json_query(TERMS_SQL_DOCKER.replace("__SOURCE_NAME__", sql_literal(args.source_name))),
        args,
    )
    return (
        tuple(MarketSensorProfileState.from_mapping(row) for row in profile_rows),
        tuple(MarketSensorTermState.from_mapping(row) for row in term_rows),
    )


def run_docker_json_query(sql: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    command = [
        "docker",
        "exec",
        "-i",
        args.docker_container,
        "psql",
        "-U",
        args.docker_user,
        "-d",
        args.docker_db,
        "-t",
        "-A",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        sql,
    ]
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "docker psql query failed")
    payload = result.stdout.strip()
    if not payload:
        return []
    return json.loads(payload)


def wrap_json_query(inner_sql: str) -> str:
    return f"select coalesce(json_agg(row_to_json(rows)), '[]'::json) from ({inner_sql}) rows;"


def resolve_dsn(explicit_dsn: str | None) -> str | None:
    return explicit_dsn or os.getenv("JOB_PIPELINE_DATABASE_URL") or os.getenv("DATABASE_URL")


def build_database_unavailable_report(source_name: str, error: BaseException) -> dict[str, Any]:
    return {
        "schema_version": "sensor001c.ba_remote_nationwide_controlled_activation.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "work_item": "SENSOR-001C BA Remote/Nationwide Controlled Activation",
        "source_name": source_name,
        "overall_status": "db_unavailable",
        "database_error": {
            "type": type(error).__name__,
            "message": str(error).splitlines()[0] if str(error) else "database inspection unavailable",
        },
        "findings": [],
        "next_action": "Start the database, configure a DSN, or use the docker psql fallback, then rerun SENSOR-001C.",
        "safety_boundary": {
            "read_only_review_script": True,
            "external_requests": False,
            "ingestion_run": False,
            "scheduler_mutation": False,
            "productive_activation": False,
        },
    }


def build_unsupported_source_report(source_name: str) -> dict[str, Any]:
    return {
        "schema_version": "sensor001c.ba_remote_nationwide_controlled_activation.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "work_item": "SENSOR-001C BA Remote/Nationwide Controlled Activation",
        "source_name": source_name,
        "overall_status": "unsupported_source",
        "findings": [],
        "next_action": "Create a dedicated controlled-activation work item for this source family.",
        "safety_boundary": {
            "read_only_review_script": True,
            "external_requests": False,
            "ingestion_run": False,
            "scheduler_mutation": False,
            "productive_activation": False,
        },
    }


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


PROFILES_SQL = """
select
    id,
    profile_name,
    source_name,
    search_term,
    search_location,
    search_radius_km,
    offer_type,
    page_size,
    is_active
from search_profiles
where source_name = %(source_name)s
order by profile_name
"""

TERMS_SQL = """
select
    sp.profile_name,
    st.search_term,
    st.is_active
from search_profiles sp
join search_terms st on st.search_profile_id = sp.id
where sp.source_name = %(source_name)s
order by sp.profile_name, st.search_term
"""

PROFILES_SQL_DOCKER = """
select
    id,
    profile_name,
    source_name,
    search_term,
    search_location,
    search_radius_km,
    offer_type,
    page_size,
    is_active
from search_profiles
where source_name = __SOURCE_NAME__
order by profile_name
"""

TERMS_SQL_DOCKER = """
select
    sp.profile_name,
    st.search_term,
    st.is_active
from search_profiles sp
join search_terms st on st.search_profile_id = sp.id
where sp.source_name = __SOURCE_NAME__
order by sp.profile_name, st.search_term
"""


if __name__ == "__main__":
    raise SystemExit(main())
