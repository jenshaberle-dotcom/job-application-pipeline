from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.config import get_database_config
from src.search_intelligence.candidate_fact_profile import (
    APPROVAL_TOKEN,
    PROFILE_KEY,
    SOURCE_TYPE,
    CandidateFactProfile,
    candidate_fact_rows,
    ensure_no_capability_claim_from_direction,
    load_candidate_fact_profile_json,
)


REPORT_SCHEMA = "private_candidate_fact_profile_import.v1"
LOCK_KEY = "APP-011A:private_candidate_fact_profile:default"
REQUIRED_TABLES = (
    "candidate_fact_profiles",
    "candidate_facts",
    "candidate_fact_profile_revisions",
)


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def ensure_schema(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        for table in REQUIRED_TABLES:
            cur.execute("SELECT to_regclass(%s) AS relation", (f"public.{table}",))
            row = cur.fetchone()
            if row is None or row["relation"] is None:
                raise RuntimeError(
                    f"{table} is missing; apply tracked migration "
                    "088_create_private_candidate_fact_foundation.sql first"
                )


def load_current_profile(
    conn: psycopg.Connection[Any],
    *,
    lock: bool = False,
) -> Mapping[str, Any] | None:
    lock_clause = "FOR UPDATE" if lock else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                profile_key,
                schema_version,
                profile_version,
                status,
                payload,
                payload_sha256,
                source_type,
                approved_by,
                approved_at,
                created_at,
                updated_at
            FROM candidate_fact_profiles
            WHERE profile_key = %s
            {lock_clause}
            """,
            (PROFILE_KEY,),
        )
        return cur.fetchone()


def load_persisted_counts(conn: psycopg.Connection[Any]) -> Mapping[str, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                count(*)::integer AS fact_count,
                count(*) FILTER (
                    WHERE approval_status = 'approved'
                )::integer AS approved_fact_count,
                count(*) FILTER (
                    WHERE approval_status = 'approved'
                      AND evidence_class IN (
                          'professional_employment',
                          'formal_education',
                          'portfolio_implementation',
                          'training_certification'
                      )
                )::integer AS capability_evidence_fact_count,
                count(*) FILTER (
                    WHERE approval_status = 'approved'
                      AND evidence_class = 'professional_employment'
                )::integer AS production_evidence_fact_count
            FROM candidate_facts
            WHERE profile_key = %s
            """,
            (PROFILE_KEY,),
        )
        row = cur.fetchone()
    _require(row is not None, "candidate fact count query returned no row")
    return {
        "fact_count": int(row["fact_count"]),
        "approved_fact_count": int(row["approved_fact_count"]),
        "capability_evidence_fact_count": int(row["capability_evidence_fact_count"]),
        "production_evidence_fact_count": int(row["production_evidence_fact_count"]),
    }


def _insert_revision(
    cur: psycopg.Cursor[Any],
    *,
    profile: CandidateFactProfile,
    previous: Mapping[str, Any] | None,
    applied_by: str,
) -> bool:
    previous_payload = None if previous is None else previous["payload"]
    previous_sha256 = None if previous is None else previous["payload_sha256"]
    cur.execute(
        """
        INSERT INTO candidate_fact_profile_revisions (
            profile_key,
            revision_key,
            previous_payload,
            next_payload,
            previous_sha256,
            next_sha256,
            applied_by
        )
        VALUES (
            %(profile_key)s,
            %(revision_key)s,
            %(previous_payload)s,
            %(next_payload)s,
            %(previous_sha256)s,
            %(next_sha256)s,
            %(applied_by)s
        )
        ON CONFLICT (profile_key, revision_key) DO NOTHING
        RETURNING id
        """,
        {
            "profile_key": profile.profile_key,
            "revision_key": profile.revision_key,
            "previous_payload": (
                None if previous_payload is None else Jsonb(previous_payload)
            ),
            "next_payload": Jsonb(profile.canonical_payload()),
            "previous_sha256": previous_sha256,
            "next_sha256": profile.payload_sha256,
            "applied_by": applied_by,
        },
    )
    return cur.fetchone() is not None


def _upsert_profile(cur: psycopg.Cursor[Any], profile: CandidateFactProfile) -> None:
    cur.execute(
        """
        INSERT INTO candidate_fact_profiles (
            profile_key,
            schema_version,
            profile_version,
            status,
            payload,
            payload_sha256,
            source_type,
            approved_by,
            approved_at
        )
        VALUES (
            %(profile_key)s,
            %(schema_version)s,
            %(profile_version)s,
            %(status)s,
            %(payload)s,
            %(payload_sha256)s,
            %(source_type)s,
            %(approved_by)s,
            %(approved_at)s
        )
        ON CONFLICT (profile_key)
        DO UPDATE SET
            schema_version = EXCLUDED.schema_version,
            profile_version = EXCLUDED.profile_version,
            status = EXCLUDED.status,
            payload = EXCLUDED.payload,
            payload_sha256 = EXCLUDED.payload_sha256,
            source_type = EXCLUDED.source_type,
            approved_by = EXCLUDED.approved_by,
            approved_at = EXCLUDED.approved_at,
            updated_at = now()
        """,
        {
            "profile_key": profile.profile_key,
            "schema_version": profile.schema_version,
            "profile_version": profile.profile_version,
            "status": profile.status,
            "payload": Jsonb(profile.canonical_payload()),
            "payload_sha256": profile.payload_sha256,
            "source_type": SOURCE_TYPE,
            "approved_by": profile.approved_by,
            "approved_at": profile.approved_at,
        },
    )


def _replace_facts(cur: psycopg.Cursor[Any], profile: CandidateFactProfile) -> None:
    cur.execute("DELETE FROM candidate_facts WHERE profile_key = %s", (profile.profile_key,))
    rows = candidate_fact_rows(profile)
    for row in rows:
        cur.execute(
            """
            INSERT INTO candidate_facts (
                profile_key,
                fact_key,
                category,
                evidence_class,
                approval_status,
                statement,
                capability_tags,
                limitations,
                provenance,
                valid_from,
                valid_until,
                approved_by,
                approved_at,
                fact_payload
            )
            VALUES (
                %(profile_key)s,
                %(fact_key)s,
                %(category)s,
                %(evidence_class)s,
                %(approval_status)s,
                %(statement)s,
                %(capability_tags)s,
                %(limitations)s,
                %(provenance)s,
                %(valid_from)s,
                %(valid_until)s,
                %(approved_by)s,
                %(approved_at)s,
                %(fact_payload)s
            )
            """,
            {
                **row,
                "capability_tags": Jsonb(row["capability_tags"]),
                "limitations": Jsonb(row["limitations"]),
                "provenance": Jsonb(row["provenance"]),
                "fact_payload": Jsonb(row["fact_payload"]),
            },
        )


def apply_profile(
    conn: psycopg.Connection[Any],
    *,
    profile: CandidateFactProfile,
    applied_by: str,
) -> tuple[bool, bool]:
    _require(profile.status == "approved", "only an approved candidate fact profile may be applied")
    _require(
        profile.approved_by == applied_by,
        "applied_by must match the profile approver",
    )
    ensure_no_capability_claim_from_direction(profile.facts)

    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (LOCK_KEY,))

    previous = load_current_profile(conn, lock=True)
    if previous is not None and previous["payload_sha256"] == profile.payload_sha256:
        conn.commit()
        return False, False
    if previous is not None and previous["profile_version"] == profile.profile_version:
        raise RuntimeError(
            "candidate profile content changed without a new profile_version"
        )

    with conn.cursor() as cur:
        revision_inserted = _insert_revision(
            cur,
            profile=profile,
            previous=previous,
            applied_by=applied_by,
        )
        _require(revision_inserted, "candidate profile revision already exists with different current state")
        _upsert_profile(cur, profile)
        _replace_facts(cur, profile)

    persisted = load_current_profile(conn, lock=False)
    _require(persisted is not None, "candidate profile was not persisted")
    _require(
        persisted["payload_sha256"] == profile.payload_sha256,
        "persisted candidate profile hash mismatch",
    )
    counts = load_persisted_counts(conn)
    summary = profile.redacted_summary()
    for key in (
        "fact_count",
        "approved_fact_count",
        "capability_evidence_fact_count",
        "production_evidence_fact_count",
    ):
        _require(counts[key] == summary[key], f"persisted candidate fact count mismatch: {key}")

    conn.commit()
    return True, True


def write_report(report: Mapping[str, Any], report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = report_dir / f"private_candidate_fact_profile_import_{timestamp}.json"
    path.write_text(
        json.dumps(_json_safe(report), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate or import a private approved candidate fact profile."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--applied-by", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    applied_by = args.applied_by.strip()
    if not applied_by:
        raise SystemExit("applied_by must not be blank")
    if not args.input.is_file():
        raise SystemExit("candidate fact profile input file does not exist")
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit("invalid candidate fact profile approval token")

    profile = load_candidate_fact_profile_json(args.input.read_text(encoding="utf-8"))
    summary = profile.redacted_summary()

    conn = connect()
    try:
        ensure_schema(conn)
        current = load_current_profile(conn)
        current_hash = None if current is None else current["payload_sha256"]
        would_change = current_hash != profile.payload_sha256
        revision_inserted = False
        profile_updated = False

        if args.apply:
            revision_inserted, profile_updated = apply_profile(
                conn,
                profile=profile,
                applied_by=applied_by,
            )
        else:
            conn.rollback()

        report = {
            "schema_version": REPORT_SCHEMA,
            "review_output_only_not_pipeline_input": True,
            "mode": "apply" if args.apply else "plan_only",
            "profile": summary,
            "existing_payload_sha256": current_hash,
            "would_change": would_change,
            "revision_inserted": revision_inserted,
            "profile_updated": profile_updated,
            "boundaries": {
                "personal_statements_emitted": False,
                "provenance_references_emitted": False,
                "capability_fit_decision_created": False,
                "weekly_hours_inferred": False,
                "ranking_scores_created": False,
                "hard_filter_pass_forced": False,
                "network_requests": 0,
                "provider_requests": 0,
                "source_or_scheduler_activation": False,
                "application_action_performed": False,
            },
        }
        report_path = write_report(report, args.report_dir)

        print("Private candidate fact profile import")
        print(f"mode: {report['mode']}")
        print(f"profile_key: {profile.profile_key}")
        print(f"profile_version: {profile.profile_version}")
        print(f"status: {profile.status}")
        print(f"payload_sha256: {profile.payload_sha256}")
        print(f"fact_count: {summary['fact_count']}")
        print(f"approved_fact_count: {summary['approved_fact_count']}")
        print(
            "capability_evidence_fact_count: "
            f"{summary['capability_evidence_fact_count']}"
        )
        print(
            "production_evidence_fact_count: "
            f"{summary['production_evidence_fact_count']}"
        )
        print(f"would_change: {would_change}")
        print(f"revision_inserted: {revision_inserted}")
        print(f"profile_updated: {profile_updated}")
        print("capability_fit_decision_created: false")
        print(f"report: {report_path}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
