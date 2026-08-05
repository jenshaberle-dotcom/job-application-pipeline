from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.ingestion.eon_controlled_pilot import (
    EXPECTED_EXTERNAL_JOB_ID,
    EXPECTED_TITLE,
    PILOT_SOURCE_NAME,
    is_authorized_pilot_raw_data,
)
from src.search_intelligence.successfactors_locations import (
    SuccessFactorsLocationEvidence,
    extract_successfactors_locations,
)


PROJECTION_KEY = "EON-MULTI-LOCATION-PROJECTION-001"
APPROVAL_TOKEN = PROJECTION_KEY
EXPECTED_RAW_JOB_ID = 26342
EXPECTED_SILVER_JOB_ID = 466
EXPECTED_LEGACY_CITY = "Essen"
EXPECTED_LOCATIONS = (
    ("Essen", "DE"),
    ("Hannover", "DE"),
    ("München", "DE"),
)
EXPECTED_READINESS = "hard_filter_evidence_required"
REPORT_SCHEMA = "eon_multi_location_projection_execution.v1"


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def load_bound_job(
    conn: psycopg.Connection[Any],
    *,
    raw_job_id: int,
    silver_job_id: int,
    lock: bool = False,
) -> Mapping[str, Any]:
    lock_clause = "FOR SHARE OF r, s" if lock else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                r.id AS raw_job_id,
                s.id AS silver_job_id,
                r.source_name,
                r.external_job_id,
                r.raw_data,
                s.title,
                s.city,
                s.normalized_location,
                s.canonical_key_candidate
            FROM raw_jobs r
            JOIN silver_jobs s
              ON s.raw_job_id = r.id
            WHERE r.id = %s
              AND s.id = %s
            {lock_clause}
            """,
            (raw_job_id, silver_job_id),
        )
        rows = cur.fetchall()
    if len(rows) != 1:
        raise ValueError(
            "expected exactly one joined raw/Silver E.ON job, "
            f"found {len(rows)}"
        )
    return rows[0]


def ensure_location_schema(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.silver_job_locations') AS relation")
        row = cur.fetchone()
    if row is None or row["relation"] is None:
        raise RuntimeError(
            "silver_job_locations is missing; apply tracked migration "
            "086_create_silver_job_locations.sql first"
        )


def load_readiness(
    conn: psycopg.Connection[Any],
    *,
    silver_job_id: int,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT product_readiness_status
            FROM gold_product_v1_job_readiness
            WHERE silver_job_id = %s
            """,
            (silver_job_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError("Product V1 readiness row is missing")
    return str(row["product_readiness_status"])


def load_existing_locations(
    conn: psycopg.Connection[Any],
    *,
    silver_job_id: int,
    lock: bool = False,
) -> list[Mapping[str, Any]]:
    lock_clause = "FOR UPDATE" if lock else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                city,
                country_code,
                is_primary,
                evidence_source,
                evidence_text,
                observed_at_utc
            FROM silver_job_locations
            WHERE silver_job_id = %s
            ORDER BY lower(city), lower(country_code)
            {lock_clause}
            """,
            (silver_job_id,),
        )
        return list(cur.fetchall())


def bind_and_extract(
    row: Mapping[str, Any],
    *,
    raw_job_id: int,
    silver_job_id: int,
) -> tuple[SuccessFactorsLocationEvidence, ...]:
    if int(row["raw_job_id"]) != raw_job_id:
        raise ValueError("raw job ID mismatch")
    if int(row["silver_job_id"]) != silver_job_id:
        raise ValueError("Silver job ID mismatch")
    if raw_job_id != EXPECTED_RAW_JOB_ID or silver_job_id != EXPECTED_SILVER_JOB_ID:
        raise ValueError("runner is bound to the exact E.ON pilot IDs")
    if row["source_name"] != PILOT_SOURCE_NAME:
        raise ValueError("E.ON source mismatch")
    if row["external_job_id"] != EXPECTED_EXTERNAL_JOB_ID:
        raise ValueError("E.ON external job ID mismatch")
    if row["title"] != EXPECTED_TITLE:
        raise ValueError("E.ON title mismatch")
    if row["city"] != EXPECTED_LEGACY_CITY:
        raise ValueError("legacy Silver city changed unexpectedly")

    raw_data = _mapping(row["raw_data"], "raw_data")
    if not is_authorized_pilot_raw_data(raw_data):
        raise ValueError("raw job is not the authorized E.ON pilot dataset")
    job = _mapping(raw_data.get("job"), "raw_data.job")
    description = job.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("stored E.ON detail description is missing")

    locations = extract_successfactors_locations(description)
    observed = tuple((item.city, item.country) for item in locations)
    if observed != EXPECTED_LOCATIONS:
        raise ValueError(
            "unexpected E.ON detail location evidence: "
            f"expected={EXPECTED_LOCATIONS!r} actual={observed!r}"
        )
    return locations


def _canonical_existing(
    rows: list[Mapping[str, Any]],
) -> tuple[tuple[str, str, bool], ...]:
    return tuple(
        sorted(
            (
                str(row["city"]),
                str(row["country_code"]),
                bool(row["is_primary"]),
            )
            for row in rows
        )
    )


def _expected_existing() -> tuple[tuple[str, str, bool], ...]:
    return tuple(
        sorted(
            (city, country, city == EXPECTED_LEGACY_CITY)
            for city, country in EXPECTED_LOCATIONS
        )
    )


def validate_existing_rows(rows: list[Mapping[str, Any]]) -> None:
    if not rows:
        return
    if _canonical_existing(rows) != _expected_existing():
        raise RuntimeError("conflicting Silver location projection already exists")
    for row in rows:
        if row["evidence_source"] != "successfactors_detail_location_field":
            raise RuntimeError("existing Silver location evidence source conflicts")


def insert_locations(
    conn: psycopg.Connection[Any],
    *,
    silver_job_id: int,
    locations: tuple[SuccessFactorsLocationEvidence, ...],
    observed_at_utc: str | None,
) -> int:
    inserted = 0
    with conn.cursor() as cur:
        for location in locations:
            cur.execute(
                """
                INSERT INTO silver_job_locations (
                    silver_job_id,
                    city,
                    country_code,
                    is_primary,
                    evidence_source,
                    evidence_text,
                    observed_at_utc
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    silver_job_id,
                    location.city,
                    location.country,
                    location.city == EXPECTED_LEGACY_CITY,
                    location.evidence_source,
                    location.evidence_text,
                    observed_at_utc,
                ),
            )
            inserted += cur.rowcount
    return inserted


def apply_projection(
    *,
    raw_job_id: int,
    silver_job_id: int,
    expected_locations: tuple[SuccessFactorsLocationEvidence, ...],
) -> tuple[int, list[Mapping[str, Any]], str]:
    conn = connect()
    try:
        with conn.transaction():
            ensure_location_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"{PROJECTION_KEY}:{silver_job_id}",),
                )
            row = load_bound_job(
                conn,
                raw_job_id=raw_job_id,
                silver_job_id=silver_job_id,
                lock=True,
            )
            rebuilt = bind_and_extract(
                row,
                raw_job_id=raw_job_id,
                silver_job_id=silver_job_id,
            )
            if rebuilt != expected_locations:
                raise RuntimeError("location evidence changed between preflight and Apply")

            before = load_existing_locations(
                conn,
                silver_job_id=silver_job_id,
                lock=True,
            )
            validate_existing_rows(before)
            raw_data = _mapping(row["raw_data"], "raw_data")
            observed_at = raw_data.get("observed_at_utc")
            if observed_at is not None and not isinstance(observed_at, str):
                raise ValueError("observed_at_utc must be a string when present")
            inserted = insert_locations(
                conn,
                silver_job_id=silver_job_id,
                locations=rebuilt,
                observed_at_utc=observed_at,
            )
            after = load_existing_locations(conn, silver_job_id=silver_job_id)
            validate_existing_rows(after)
            if _canonical_existing(after) != _expected_existing():
                raise RuntimeError("post-Apply Silver location projection is incomplete")
            if row["city"] != EXPECTED_LEGACY_CITY:
                raise RuntimeError("legacy Silver city mutated during location projection")
            readiness_after = load_readiness(conn, silver_job_id=silver_job_id)
            if readiness_after != EXPECTED_READINESS:
                raise RuntimeError(
                    "location projection unexpectedly changed Product V1 readiness: "
                    f"expected={EXPECTED_READINESS} actual={readiness_after}"
                )
        return inserted, after, readiness_after
    finally:
        conn.close()


def _json_safe(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def write_report(
    *,
    output_dir: Path,
    mode: str,
    raw_job_id: int,
    silver_job_id: int,
    readiness_before: str,
    readiness_after: str | None,
    legacy_city: str,
    proposed_locations: tuple[SuccessFactorsLocationEvidence, ...],
    existing_before: list[Mapping[str, Any]],
    existing_after: list[Mapping[str, Any]] | None,
    inserted_count: int,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_dir / f"eon_multi_location_projection_{stamp}.json"
    payload = {
        "schema_version": REPORT_SCHEMA,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "mode": mode,
        "projection_key": PROJECTION_KEY,
        "raw_job_id": raw_job_id,
        "silver_job_id": silver_job_id,
        "readiness_before": readiness_before,
        "readiness_after": readiness_after,
        "legacy_city": legacy_city,
        "legacy_city_unchanged": legacy_city == EXPECTED_LEGACY_CITY,
        "proposed_locations": [
            location.canonical_payload() for location in proposed_locations
        ],
        "existing_locations_before": _json_safe(existing_before),
        "existing_locations_after": _json_safe(existing_after or []),
        "locations_inserted": inserted_count,
        "review_output_only_not_pipeline_input": True,
        "boundary": {
            "network_requests": 0,
            "provider_requests": 0,
            "scheduler_changed": False,
            "connector_activated": False,
            "bronze_rows_created": 0,
            "silver_job_rows_created": 0,
            "legacy_silver_city_changed": False,
            "ranking_scores_created": False,
            "hard_filter_decision_created": False,
            "application_action_performed": False,
            "exact_eon_pilot_job_only": True,
        },
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Project the exact E.ON pilot job's stored multi-location evidence "
            "into normalized Silver location rows."
        )
    )
    parser.add_argument("--raw-job-id", type=int, required=True)
    parser.add_argument("--silver-job-id", type=int, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit(f"--apply requires --approval-token {APPROVAL_TOKEN}")
    if not args.apply and args.approval_token:
        raise SystemExit("--approval-token is accepted only together with --apply")

    try:
        conn = connect()
        try:
            ensure_location_schema(conn)
            row = load_bound_job(
                conn,
                raw_job_id=args.raw_job_id,
                silver_job_id=args.silver_job_id,
            )
            locations = bind_and_extract(
                row,
                raw_job_id=args.raw_job_id,
                silver_job_id=args.silver_job_id,
            )
            readiness_before = load_readiness(
                conn,
                silver_job_id=args.silver_job_id,
            )
            if readiness_before != EXPECTED_READINESS:
                raise RuntimeError(
                    "unexpected pre-projection Product V1 readiness: "
                    f"expected={EXPECTED_READINESS} actual={readiness_before}"
                )
            existing_before = load_existing_locations(
                conn,
                silver_job_id=args.silver_job_id,
            )
            validate_existing_rows(existing_before)
            conn.rollback()
        finally:
            conn.close()

        inserted_count = 0
        existing_after: list[Mapping[str, Any]] | None = None
        readiness_after: str | None = None
        if args.apply:
            inserted_count, existing_after, readiness_after = apply_projection(
                raw_job_id=args.raw_job_id,
                silver_job_id=args.silver_job_id,
                expected_locations=locations,
            )

        report_path = write_report(
            output_dir=args.output_dir,
            mode="apply" if args.apply else "plan_only",
            raw_job_id=args.raw_job_id,
            silver_job_id=args.silver_job_id,
            readiness_before=readiness_before,
            readiness_after=readiness_after,
            legacy_city=str(row["city"]),
            proposed_locations=locations,
            existing_before=existing_before,
            existing_after=existing_after,
            inserted_count=inserted_count,
        )
    except (OSError, ValueError, RuntimeError, psycopg.Error) as exc:
        raise SystemExit(str(exc)) from exc

    print("E.ON multi-location projection")
    print(f"mode: {'apply' if args.apply else 'plan_only'}")
    print(f"raw_job_id: {args.raw_job_id}")
    print(f"silver_job_id: {args.silver_job_id}")
    print(f"legacy_city: {row['city']}")
    print("locations: " + ", ".join(item.city for item in locations))
    print(f"readiness_before: {readiness_before}")
    print(f"locations_inserted: {inserted_count}")
    if readiness_after is not None:
        print(f"readiness_after: {readiness_after}")
        print("legacy_city_unchanged: true")
    else:
        print("network_requests: 0")
        print("database_mutation: false")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
