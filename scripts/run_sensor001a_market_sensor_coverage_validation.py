from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg

from src.search_intelligence.market_sensor_coverage import (
    MarketSensorProfile,
    assess_all_market_sensors,
    assess_market_sensor_coverage,
)

EXPORTS = ROOT / "exports"

PROFILE_KEY_COLUMNS = ("profile_key", "name", "profile_name", "key", "slug")
SOURCE_COLUMNS = ("source_name", "source_key", "source", "source_identifier")
LOCATION_COLUMNS = ("search_location", "location", "target_location")
RADIUS_COLUMNS = ("search_radius_km", "radius_km", "radius", "umkreis")
ACTIVE_COLUMNS = ("is_active", "active", "enabled")
TERM_COLUMNS = ("search_term", "term", "keyword", "query")
REMOTE_CAPABILITY_COLUMNS = ("supports_remote_filter", "remote_filter_supported")


def resolve_dsn(explicit_dsn: str | None) -> str:
    return explicit_dsn or os.getenv("JOB_PIPELINE_DATABASE_URL") or os.getenv("DATABASE_URL") or ""


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def pick_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    available = {column.lower(): column for column in columns}
    for candidate in candidates:
        if candidate.lower() in available:
            return available[candidate.lower()]
    return None


def as_bool(value: object, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() not in {"0", "false", "f", "no", "n", "disabled", "inactive"}


def as_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def get_table_columns(cursor: psycopg.Cursor[Any], table_name: str) -> tuple[str, ...]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    return tuple(str(row[0]) for row in cursor.fetchall())


def fetch_rows(cursor: psycopg.Cursor[Any], table_name: str) -> list[dict[str, Any]]:
    columns = get_table_columns(cursor, table_name)
    if not columns:
        return []
    quoted = ", ".join(f'"{column}"' for column in columns)
    cursor.execute(f"SELECT {quoted} FROM {table_name}")
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def load_profiles_from_db(cursor: psycopg.Cursor[Any]) -> tuple[MarketSensorProfile, ...]:
    profile_rows = fetch_rows(cursor, "search_profiles")
    term_rows = fetch_rows(cursor, "search_terms")

    if not profile_rows:
        return ()

    profile_columns = tuple(profile_rows[0].keys())
    term_columns = tuple(term_rows[0].keys()) if term_rows else ()

    key_col = pick_column(profile_columns, PROFILE_KEY_COLUMNS)
    source_col = pick_column(profile_columns, SOURCE_COLUMNS)
    location_col = pick_column(profile_columns, LOCATION_COLUMNS)
    radius_col = pick_column(profile_columns, RADIUS_COLUMNS)
    active_col = pick_column(profile_columns, ACTIVE_COLUMNS)
    remote_capability_col = pick_column(profile_columns, REMOTE_CAPABILITY_COLUMNS)

    if not source_col:
        raise RuntimeError("search_profiles has no recognizable source column")

    term_profile_col = pick_column(term_columns, ("search_profile_id", "profile_id"))
    term_text_col = pick_column(term_columns, TERM_COLUMNS)
    term_active_col = pick_column(term_columns, ACTIVE_COLUMNS)

    terms_by_profile_id: dict[object, list[str]] = defaultdict(list)
    if term_profile_col and term_text_col:
        for row in term_rows:
            if not as_bool(row.get(term_active_col), default=True):
                continue
            profile_id = row.get(term_profile_col)
            term = row.get(term_text_col)
            if profile_id is not None and term:
                terms_by_profile_id[profile_id].append(str(term))

    profiles: list[MarketSensorProfile] = []
    for row in profile_rows:
        profile_id = row.get("id")
        profile_key = str(row.get(key_col) if key_col else profile_id)
        source_name = str(row[source_col])
        profiles.append(
            MarketSensorProfile(
                profile_key=profile_key,
                source_name=source_name,
                search_location=str(row[location_col]) if location_col and row.get(location_col) is not None else None,
                search_radius_km=as_int(row.get(radius_col)) if radius_col else None,
                search_terms=tuple(terms_by_profile_id.get(profile_id, ())),
                is_active=as_bool(row.get(active_col), default=True) if active_col else True,
                supports_remote_filter=as_bool(row.get(remote_capability_col), default=False)
                if remote_capability_col
                else False,
                raw=row,
            )
        )
    return tuple(profiles)


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# SENSOR-001A Market Sensor Coverage Validation",
        "",
        f"Generated at: `{report['generated_at_utc']}`",
        "",
        "Safety boundary: read-only database transaction, no external requests, no pipeline mutation.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{report['overall_status']}`",
        f"- Sources assessed: `{len(report['assessments'])}`",
        "- Required generic intent: `search_germany_wide_remote_options`",
        "",
        "## Assessments",
        "",
    ]
    for item in report["assessments"]:
        lines.extend(
            [
                f"### {item['source_name']}",
                "",
                f"- Status: `{item['status']}`",
                f"- Active profiles: `{item['active_profile_count']}`",
                f"- Local target: `{item['local_target']['status']}` via {item['local_target']['matching_profiles']}",
                f"- Germany-wide remote options: `{item['remote_nationwide_target']['status']}` via {item['remote_nationwide_target']['matching_profiles']}",
                f"- Gaps: `{item['coverage_gaps']}`",
                f"- Next action: `{item['next_action']}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_report(profiles: tuple[MarketSensorProfile, ...], source_name: str | None) -> dict[str, Any]:
    if source_name:
        assessments = (assess_market_sensor_coverage(source_name, profiles),)
    else:
        assessments = assess_all_market_sensors(profiles)
    assessment_dicts = [assessment.as_dict() for assessment in assessments]
    overall_status = "pass" if all(item["status"] == "pass" for item in assessment_dicts) else "gap_detected"
    return {
        "schema_version": "sensor001a.market_sensor_coverage_validation.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "safety_boundary": {
            "read_only": True,
            "external_requests": False,
            "database_writes": False,
            "pipeline_mutation": False,
            "candidate_or_gate_mutation": False,
            "connector_activation": False,
        },
        "work_item": "SENSOR-001A Market Sensor Remote/Nationwide Coverage Validation",
        "generic_requirement": "Every market sensor must make Germany-wide remote-option coverage explicit; BA is only the first concrete validation target.",
        "overall_status": overall_status,
        "profiles_loaded": len(profiles),
        "assessments": assessment_dicts,
    }


def build_database_unavailable_report(source_name: str | None, error: BaseException) -> dict[str, Any]:
    return {
        "schema_version": "sensor001a.market_sensor_coverage_validation.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "safety_boundary": {
            "read_only": True,
            "external_requests": False,
            "database_writes": False,
            "pipeline_mutation": False,
            "candidate_or_gate_mutation": False,
            "connector_activation": False,
        },
        "work_item": "SENSOR-001A Market Sensor Remote/Nationwide Coverage Validation",
        "generic_requirement": "Every market sensor must make Germany-wide remote-option coverage explicit; BA is only the first concrete validation target.",
        "overall_status": "db_unavailable",
        "profiles_loaded": 0,
        "source_name_filter": source_name,
        "assessments": [],
        "database_error": {
            "type": type(error).__name__,
            "message": str(error).splitlines()[0] if str(error) else "database connection unavailable",
        },
        "next_action": "Start the local database or pass a valid --dsn, then rerun the read-only coverage validation.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generic market-sensor local and remote/nationwide coverage.")
    parser.add_argument("--dsn", default=None, help="Optional PostgreSQL DSN. Defaults to JOB_PIPELINE_DATABASE_URL / DATABASE_URL / PG* env vars.")
    parser.add_argument("--source-name", default=None, help="Optional source_name filter, e.g. bundesagentur_fuer_arbeit.")
    parser.add_argument("--output-dir", default=str(EXPORTS))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = now_stamp()
    json_path = output_dir / f"sensor001a_market_sensor_coverage_validation_{stamp}.json"
    md_path = output_dir / f"sensor001a_market_sensor_coverage_validation_{stamp}.md"

    dsn = resolve_dsn(args.dsn)
    try:
        with psycopg.connect(dsn) as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                with conn.cursor() as cursor:
                    profiles = load_profiles_from_db(cursor)
                    report = build_report(profiles, args.source_name)
    except psycopg.OperationalError as error:
        report = build_database_unavailable_report(args.source_name, error)

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print("# SENSOR-001A Market Sensor Coverage Validation")
    print(f"overall_status={report['overall_status']}")
    print(f"profiles_loaded={report['profiles_loaded']}")
    if report.get("database_error"):
        error = report["database_error"]
        print(f"database_error={error['type']}: {error['message']}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")

    if report["overall_status"] == "pass":
        return 0
    if report["overall_status"] == "db_unavailable":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
