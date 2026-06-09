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
from src.search_intelligence.sensor001g_ba_remote_controlled_activation_gate import (
    CONFIRMATION_TOKEN,
    build_sensor001g_activation_gate,
    render_markdown,
)

DEFAULT_DOCKER_CONTAINER = "job_pipeline_postgres"
DEFAULT_DOCKER_USER = "job_user"
DEFAULT_DOCKER_DB = "job_pipeline"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or apply SENSOR-001G BA remote/nationwide controlled activation gate."
    )
    parser.add_argument("--sensor001f-json", default=None, help="Path to a SENSOR-001F JSON export. Defaults to latest exports/sensor001f_*.json.")
    parser.add_argument("--apply", action="store_true", help="Apply the bounded profile activation after explicit approval and confirmation.")
    parser.add_argument("--confirm", default=None, help=f"Required with --apply. Expected: {CONFIRMATION_TOKEN}")
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
    json_path = output_dir / f"sensor001g_ba_remote_controlled_activation_gate_{stamp}.json"
    md_path = output_dir / f"sensor001g_ba_remote_controlled_activation_gate_{stamp}.md"

    try:
        sensor001f_path = Path(args.sensor001f_json) if args.sensor001f_json else latest_sensor001f_report_path(output_dir)
        sensor001f_report = json.loads(sensor001f_path.read_text(encoding="utf-8"))
        profiles, terms, access = load_state(args)
        report_obj = build_sensor001g_activation_gate(
            sensor001f_report=sensor001f_report,
            profiles=profiles,
            terms=terms,
            apply_requested=args.apply,
            confirmation_token=args.confirm,
            apply_executed=False,
        )
        report = report_obj.as_dict()
        report["sensor001f_input_path"] = str(sensor001f_path)
        report["db_access_method"] = access

        if args.apply and report.get("overall_status") == "activation_apply_authorized":
            updated = apply_activation(args)
            profiles_after, terms_after, access_after = load_state(args)
            report = build_sensor001g_activation_gate(
                sensor001f_report=sensor001f_report,
                profiles=profiles_after,
                terms=terms_after,
                apply_requested=True,
                confirmation_token=args.confirm,
                apply_executed=bool(updated),
            ).as_dict()
            report["sensor001f_input_path"] = str(sensor001f_path)
            report["db_access_method"] = access_after
            report["activation_update_rows"] = updated

        exit_code = 0 if report.get("overall_status") in {
            "activation_apply_ready",
            "activation_apply_blocked_by_missing_confirmation",
            "activation_applied",
            "already_active_controlled_profile",
        } else 1
    except Exception as error:
        report = build_failure_report(args.source_name, error)
        exit_code = 2

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print("# SENSOR-001G BA Remote/Nationwide Controlled Activation Gate")
    print(f"overall_status={report.get('overall_status')}")
    print(f"recommended_decision={report.get('recommended_decision')}")
    print(f"confidence={report.get('confidence')}")
    if report.get("db_access_method"):
        print(f"db_access_method={report['db_access_method']}")
    if report.get("database_error"):
        error = report["database_error"]
        print(f"database_error={error['type']}: {error['message']}")
    print(f"confirmation_token_required={report.get('confirmation_token_required')}")
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
    return profiles, terms


def load_state_with_docker_psql(
    args: argparse.Namespace,
) -> tuple[tuple[MarketSensorProfileState, ...], tuple[MarketSensorTermState, ...]]:
    profile_rows = run_docker_json_query(wrap_json_query(PROFILES_SQL_DOCKER.replace("__SOURCE_NAME__", sql_literal(args.source_name))), args)
    term_rows = run_docker_json_query(wrap_json_query(TERMS_SQL_DOCKER.replace("__SOURCE_NAME__", sql_literal(args.source_name))), args)
    return (
        tuple(MarketSensorProfileState.from_mapping(row) for row in profile_rows),
        tuple(MarketSensorTermState.from_mapping(row) for row in term_rows),
    )


def apply_activation(args: argparse.Namespace) -> list[dict[str, Any]]:
    dsn = resolve_dsn(args.dsn)
    if dsn:
        return apply_activation_with_psycopg(dsn)
    if args.no_docker_fallback:
        raise RuntimeError("No DSN configured and docker fallback disabled.")
    return run_docker_json_query(APPLY_ACTIVATION_SQL_DOCKER, args)


def apply_activation_with_psycopg(dsn: str) -> list[dict[str, Any]]:
    import psycopg

    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                cursor.execute(APPLY_ACTIVATION_SQL, {"profile_name": BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME, "source_name": BA_SOURCE_NAME})
                rows = cursor.fetchall()
                columns = [desc.name for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]


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


def latest_sensor001f_report_path(output_dir: Path) -> Path:
    matches = sorted(output_dir.glob("sensor001f_ba_remote_result_decision_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError("No SENSOR-001F JSON export found. Pass --sensor001f-json explicitly.")
    return matches[0]


def wrap_json_query(inner_sql: str) -> str:
    return f"select coalesce(json_agg(row_to_json(rows)), '[]'::json) from ({inner_sql}) rows;"


def resolve_dsn(explicit_dsn: str | None) -> str | None:
    return explicit_dsn or os.getenv("JOB_PIPELINE_DATABASE_URL") or os.getenv("DATABASE_URL")


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_failure_report(source_name: str, error: BaseException) -> dict[str, Any]:
    return {
        "schema_version": "sensor001g.ba_remote_nationwide_controlled_activation_gate.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "work_item": "SENSOR-001G BA Remote/Nationwide Controlled Activation Gate",
        "source_name": source_name,
        "overall_status": "activation_gate_failed",
        "database_error": {"type": type(error).__name__, "message": str(error).splitlines()[0] if str(error) else "unknown error"},
        "findings": [],
        "next_action": "Inspect the failure and rerun after repair.",
        "safety_boundary": {
            "external_requests": False,
            "database_reads": False,
            "database_writes": False,
            "profile_activation_write": False,
            "raw_jobs_write": False,
            "ingestion_run_write": False,
            "scheduler_mutation": False,
            "candidate_or_gate_mutation": False,
            "connector_activation": False,
            "bronze_silver_gold_mutation": False,
        },
        "confirmation_token_required": CONFIRMATION_TOKEN,
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

APPLY_ACTIVATION_SQL = """
UPDATE search_profiles
SET is_active = TRUE
WHERE profile_name = %(profile_name)s
  AND source_name = %(source_name)s
  AND is_active = FALSE
RETURNING id, profile_name, source_name, is_active;
"""

APPLY_ACTIVATION_SQL_DOCKER = """
WITH updated AS (
    UPDATE search_profiles
    SET is_active = TRUE
    WHERE profile_name = 'ba_data_engineering_remote_nationwide_review'
      AND source_name = 'bundesagentur_fuer_arbeit'
      AND is_active = FALSE
    RETURNING id, profile_name, source_name, is_active
)
SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json) FROM updated;
"""


if __name__ == "__main__":
    raise SystemExit(main())
