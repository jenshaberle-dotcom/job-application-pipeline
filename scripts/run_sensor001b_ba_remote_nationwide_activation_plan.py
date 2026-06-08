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

from src.search_intelligence.market_sensor_activation_plan import (
    BA_SOURCE_NAME,
    MarketSensorProfile,
    MarketSensorSearchTerm,
    build_ba_remote_nationwide_activation_plan,
    render_activation_sql_draft,
)

DEFAULT_DOCKER_CONTAINER = "job_pipeline_postgres"
DEFAULT_DOCKER_USER = "job_user"
DEFAULT_DOCKER_DB = "job_pipeline"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate SENSOR-001B BA remote/nationwide activation plan without mutating the database."
    )
    parser.add_argument("--dsn", default=None, help="Optional PostgreSQL DSN. Defaults to JOB_PIPELINE_DATABASE_URL / DATABASE_URL.")
    parser.add_argument("--source-name", default=BA_SOURCE_NAME, help="Source name to inspect. SENSOR-001B currently supports BA only.")
    parser.add_argument("--output-dir", default="exports", help="Directory for JSON/Markdown/SQL plan artifacts.")
    parser.add_argument("--docker-container", default=DEFAULT_DOCKER_CONTAINER, help="Docker container name for psql fallback.")
    parser.add_argument("--docker-user", default=DEFAULT_DOCKER_USER, help="Database user for docker psql fallback.")
    parser.add_argument("--docker-db", default=DEFAULT_DOCKER_DB, help="Database name for docker psql fallback.")
    parser.add_argument("--no-docker-fallback", action="store_true", help="Disable docker exec psql fallback when no DSN is configured.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"sensor001b_ba_remote_nationwide_activation_plan_{stamp}.json"
    md_path = output_dir / f"sensor001b_ba_remote_nationwide_activation_plan_{stamp}.md"
    sql_path = output_dir / f"sensor001b_ba_remote_nationwide_activation_plan_{stamp}.sql"

    if args.source_name != BA_SOURCE_NAME:
        report = build_unsupported_source_report(args.source_name)
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(render_markdown(report, sql_path), encoding="utf-8")
        sql_path.write_text("-- No SQL draft generated for unsupported source.\n", encoding="utf-8")
        print_summary(report, json_path, md_path, sql_path)
        return 1

    try:
        profiles, terms, access_method = load_ba_state(args)
        plan = build_ba_remote_nationwide_activation_plan(profiles, terms)
        report = plan.as_dict()
        report["db_access_method"] = access_method
        sql_draft = render_activation_sql_draft(plan)
        exit_code = 0
    except Exception as error:  # intentionally broad: produce a controlled report instead of a traceback
        report = build_database_unavailable_report(args.source_name, error)
        sql_draft = "-- No SQL draft generated because database inspection was unavailable.\n"
        exit_code = 2

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report, sql_path), encoding="utf-8")
    sql_path.write_text(sql_draft, encoding="utf-8")

    print_summary(report, json_path, md_path, sql_path)
    return exit_code


def load_ba_state(args: argparse.Namespace) -> tuple[tuple[MarketSensorProfile, ...], tuple[MarketSensorSearchTerm, ...], str]:
    dsn = resolve_dsn(args.dsn)
    if dsn:
        profiles, terms = load_ba_state_with_psycopg(dsn, args.source_name)
        return profiles, terms, "psycopg_dsn"

    if args.no_docker_fallback:
        raise RuntimeError("No DSN configured and docker fallback disabled.")

    profiles, terms = load_ba_state_with_docker_psql(args)
    return profiles, terms, "docker_exec_psql"


def load_ba_state_with_psycopg(
    dsn: str,
    source_name: str,
) -> tuple[tuple[MarketSensorProfile, ...], tuple[MarketSensorSearchTerm, ...]]:
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            with conn.cursor() as cursor:
                cursor.execute(PROFILES_SQL, {"source_name": source_name})
                profile_rows = cursor.fetchall()
                profile_columns = [desc.name for desc in cursor.description]
                profiles = tuple(MarketSensorProfile.from_mapping(dict(zip(profile_columns, row))) for row in profile_rows)

                cursor.execute(SEARCH_TERMS_SQL, {"source_name": source_name})
                term_rows = cursor.fetchall()
                term_columns = [desc.name for desc in cursor.description]
                terms = tuple(MarketSensorSearchTerm.from_mapping(dict(zip(term_columns, row))) for row in term_rows)

    return profiles, terms


def load_ba_state_with_docker_psql(
    args: argparse.Namespace,
) -> tuple[tuple[MarketSensorProfile, ...], tuple[MarketSensorSearchTerm, ...]]:
    profile_rows = run_docker_json_query(
        wrap_json_query(PROFILES_SQL_DOCKER.replace("__SOURCE_NAME__", sql_literal(args.source_name))),
        args,
    )
    term_rows = run_docker_json_query(
        wrap_json_query(SEARCH_TERMS_SQL_DOCKER.replace("__SOURCE_NAME__", sql_literal(args.source_name))),
        args,
    )
    profiles = tuple(MarketSensorProfile.from_mapping(row) for row in profile_rows)
    terms = tuple(MarketSensorSearchTerm.from_mapping(row) for row in term_rows)
    return profiles, terms


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
        "schema_version": "sensor001b.ba_remote_nationwide_activation_plan.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "work_item": "SENSOR-001B BA Remote/Nationwide Activation Plan",
        "source_name": source_name,
        "overall_status": "db_unavailable",
        "generic_requirement": (
            "Every market sensor must make local/regional coverage and Germany-wide remote-option coverage explicit."
        ),
        "safety_boundary": {
            "read_only": True,
            "external_requests": False,
            "database_writes": False,
            "pipeline_mutation": False,
            "candidate_or_gate_mutation": False,
            "connector_activation": False,
            "scheduler_mutation": False,
        },
        "database_error": {
            "type": type(error).__name__,
            "message": str(error).splitlines()[0] if str(error) else "database inspection unavailable",
        },
        "next_action": "Start the database, configure a DSN, or use the docker psql fallback, then rerun SENSOR-001B.",
    }


def build_unsupported_source_report(source_name: str) -> dict[str, Any]:
    return {
        "schema_version": "sensor001b.ba_remote_nationwide_activation_plan.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "work_item": "SENSOR-001B BA Remote/Nationwide Activation Plan",
        "source_name": source_name,
        "overall_status": "unsupported_source",
        "generic_requirement": (
            "Every market sensor must make local/regional coverage and Germany-wide remote-option coverage explicit."
        ),
        "safety_boundary": {
            "read_only": True,
            "external_requests": False,
            "database_writes": False,
            "pipeline_mutation": False,
            "candidate_or_gate_mutation": False,
            "connector_activation": False,
            "scheduler_mutation": False,
        },
        "next_action": "Extend this generic activation-plan pattern for the requested source family in a dedicated work item.",
    }


def render_markdown(report: dict[str, Any], sql_path: Path) -> str:
    lines = [
        "# SENSOR-001B BA Remote/Nationwide Activation Plan",
        "",
        f"- overall_status: `{report.get('overall_status')}`",
        f"- source_name: `{report.get('source_name')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        f"- sql_draft: `{sql_path}`",
        "",
        "## Generic requirement",
        "",
        str(report.get("generic_requirement", "")),
        "",
        "## Safety boundary",
        "",
    ]
    for key, value in report.get("safety_boundary", {}).items():
        lines.append(f"- {key}: `{value}`")

    if report.get("proposed_profile"):
        profile = report["proposed_profile"]
        lines.extend(
            [
                "",
                "## Proposed profile",
                "",
                f"- profile_name: `{profile['profile_name']}`",
                f"- source_name: `{profile['source_name']}`",
                f"- search_term: `{profile['search_term']}`",
                f"- search_location: `{profile['search_location']}`",
                f"- search_radius_km: `{profile['search_radius_km']}`",
                f"- page_size: `{profile['page_size']}`",
                f"- is_active: `{profile['is_active']}`",
                f"- coverage_mode: `{profile['coverage_mode']}`",
                "",
                "## Proposed search terms",
                "",
            ]
        )
        for term in report.get("proposed_search_terms", []):
            lines.append(f"- {term}")

    if report.get("activation_gates"):
        lines.extend(["", "## Activation gates", ""])
        for gate in report["activation_gates"]:
            lines.append(f"- {gate}")

    if report.get("database_error"):
        lines.extend(
            [
                "",
                "## Database error",
                "",
                f"- type: `{report['database_error']['type']}`",
                f"- message: `{report['database_error']['message']}`",
            ]
        )

    lines.append("")
    return "\n".join(lines)


def print_summary(report: dict[str, Any], json_path: Path, md_path: Path, sql_path: Path) -> None:
    print("# SENSOR-001B BA Remote/Nationwide Activation Plan")
    print(f"overall_status={report.get('overall_status')}")
    print(f"source_name={report.get('source_name')}")
    if report.get("db_access_method"):
        print(f"db_access_method={report['db_access_method']}")
    proposed_profile = report.get("proposed_profile")
    if proposed_profile:
        print(f"proposed_profile={proposed_profile['profile_name']}")
        print(f"proposed_profile_is_active={proposed_profile['is_active']}")
    if report.get("database_error"):
        error = report["database_error"]
        print(f"database_error={error['type']}: {error['message']}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    print(f"sql_draft={sql_path}")


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

SEARCH_TERMS_SQL = """
select
    st.id,
    st.search_profile_id,
    st.search_term,
    st.is_active
from search_terms st
join search_profiles sp on sp.id = st.search_profile_id
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

SEARCH_TERMS_SQL_DOCKER = """
select
    st.id,
    st.search_profile_id,
    st.search_term,
    st.is_active
from search_terms st
join search_profiles sp on sp.id = st.search_profile_id
where sp.source_name = __SOURCE_NAME__
order by sp.profile_name, st.search_term
"""


if __name__ == "__main__":
    raise SystemExit(main())
