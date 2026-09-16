"""F5 Slice-B application lifecycle schema qualification.

This module owns only two read-only proof phases around migration 112:

* preflight: prove migration 112 is the sole pending migration with zero checksum
  drift and that none of its target relations already exists;
* postapply: prove migration 112 is tracked successfully, its four tables and
  tracking view exist, and the schema apply seeded no application truth.

The actual mutation is intentionally delegated to the existing exact migration
runner (`scripts.apply_db_migrations --apply-exact ... --require-sole-pending`).
No provider, Gmail, email, submission, ranking or Top-5 action is performed here.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from scripts.apply_db_migrations import (
    checksum_mismatches,
    connect,
    discover_migration_files,
    load_tracked_migrations,
    pending_migrations,
    schema_migrations_exists,
    select_exact_pending_migration,
)

TARGET_MIGRATION = "112_create_authoritative_application_lifecycle.sql"
TARGET_TABLES = (
    "applications",
    "application_submissions",
    "application_lifecycle_events",
    "application_event_candidates",
)
TARGET_VIEW = "gold_product_v1_application_tracking"


class QualificationStop(RuntimeError):
    """Fail closed when real DB state does not match the requested proof phase."""


def _relation_inventory(conn: Any) -> dict[str, str]:
    names = (*TARGET_TABLES, TARGET_VIEW)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rel.relname AS name, rel.relkind AS kind
            FROM pg_class rel
            JOIN pg_namespace ns ON ns.oid = rel.relnamespace
            WHERE ns.nspname = 'public'
              AND rel.relname = ANY(%s)
            ORDER BY rel.relname
            """,
            (list(names),),
        )
        return {str(row["name"]): str(row["kind"]) for row in cur.fetchall()}


def _row_counts(conn: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        for relation in TARGET_TABLES:
            cur.execute(f'SELECT count(*)::integer AS count FROM "{relation}"')
            row = cur.fetchone()
            counts[relation] = int(row["count"])
        cur.execute(f'SELECT count(*)::integer AS count FROM "{TARGET_VIEW}"')
        row = cur.fetchone()
        counts[TARGET_VIEW] = int(row["count"])
    return counts


def _constraint_names(conn: Any, relation: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT con.conname AS name
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace ns ON ns.oid = rel.relnamespace
            WHERE ns.nspname = 'public'
              AND rel.relname = %s
            ORDER BY con.conname
            """,
            (relation,),
        )
        return [str(row["name"]) for row in cur.fetchall()]


def preflight(*, source_sha: str) -> dict[str, object]:
    migrations = discover_migration_files()
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        if not schema_migrations_exists(conn):
            raise QualificationStop("SCHEMA_MIGRATIONS_MISSING")
        tracked = load_tracked_migrations(conn)
        mismatches = checksum_mismatches(migrations, tracked)
        pending = pending_migrations(migrations, tracked)
        target, state = select_exact_pending_migration(
            migrations=migrations,
            tracked=tracked,
            migration_key=TARGET_MIGRATION,
            require_sole_pending=True,
        )
        relations = _relation_inventory(conn)

    if mismatches:
        raise QualificationStop(
            "CHECKSUM_DRIFT:" + ",".join(item.filename for item, _ in mismatches)
        )
    if state != "pending":
        raise QualificationStop(f"TARGET_NOT_PENDING:{state}")
    pending_keys = [item.migration_key for item in pending]
    if pending_keys != [TARGET_MIGRATION]:
        raise QualificationStop(f"PENDING_SET_MISMATCH:{pending_keys}")
    unexpected = sorted(relations)
    if unexpected:
        raise QualificationStop("TARGET_RELATIONS_ALREADY_EXIST:" + ",".join(unexpected))

    return {
        "schema": "jap.f5.application_lifecycle_schema_qualification.v1",
        "phase": "preflight",
        "source_sha": source_sha,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "target_migration": TARGET_MIGRATION,
        "target_version": target.version_number,
        "target_checksum_sha256": target.checksum_sha256,
        "migration_state": state,
        "pending_migrations": pending_keys,
        "checksum_mismatches": [],
        "target_relations_present": relations,
        "boundaries": {
            "db_writes": 0,
            "provider_calls": 0,
            "gmail_reads": 0,
            "email_actions": 0,
            "application_submission_actions": 0,
            "application_state_mutations": 0,
        },
    }


def postapply(*, source_sha: str) -> dict[str, object]:
    migrations = discover_migration_files()
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        if not schema_migrations_exists(conn):
            raise QualificationStop("SCHEMA_MIGRATIONS_MISSING")
        tracked = load_tracked_migrations(conn)
        mismatches = checksum_mismatches(migrations, tracked)
        pending = pending_migrations(migrations, tracked)
        target = tracked.get(TARGET_MIGRATION)
        relations = _relation_inventory(conn)

        expected_relations = {*TARGET_TABLES, TARGET_VIEW}
        missing = sorted(expected_relations - set(relations))
        if missing:
            raise QualificationStop("TARGET_RELATIONS_MISSING:" + ",".join(missing))

        counts = _row_counts(conn)
        constraints = {
            relation: _constraint_names(conn, relation) for relation in TARGET_TABLES
        }

    if mismatches:
        raise QualificationStop(
            "CHECKSUM_DRIFT:" + ",".join(item.filename for item, _ in mismatches)
        )
    if target is None:
        raise QualificationStop("TARGET_MIGRATION_UNTRACKED")
    if target.execution_status != "success":
        raise QualificationStop(f"TARGET_MIGRATION_NOT_SUCCESS:{target.execution_status}")
    if pending:
        raise QualificationStop(
            "UNEXPECTED_PENDING_MIGRATIONS:"
            + ",".join(item.migration_key for item in pending)
        )
    nonzero = {name: count for name, count in counts.items() if count != 0}
    if nonzero:
        raise QualificationStop(f"SCHEMA_APPLY_SEEDED_APPLICATION_TRUTH:{nonzero}")

    required_constraints = {
        "applications": {
            "applications_pkey",
            "applications_application_key_key",
            "chk_applications_job_identity_sha256",
        },
        "application_submissions": {
            "application_submissions_pkey",
            "application_submissions_application_id_key",
            "application_submissions_idempotency_key_key",
            "chk_application_submission_authority",
        },
        "application_lifecycle_events": {
            "application_lifecycle_events_pkey",
            "application_lifecycle_events_idempotency_key_key",
            "chk_application_lifecycle_event_authority",
        },
        "application_event_candidates": {
            "application_event_candidates_pkey",
            "uq_application_event_candidate_evidence",
            "chk_application_event_candidate_review_status",
        },
    }
    missing_constraints: dict[str, list[str]] = {}
    for relation, required in required_constraints.items():
        absent = sorted(required - set(constraints.get(relation, [])))
        if absent:
            missing_constraints[relation] = absent
    if missing_constraints:
        raise QualificationStop(f"REQUIRED_CONSTRAINTS_MISSING:{missing_constraints}")

    return {
        "schema": "jap.f5.application_lifecycle_schema_qualification.v1",
        "phase": "postapply",
        "source_sha": source_sha,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "target_migration": TARGET_MIGRATION,
        "migration_state": "applied",
        "migration_execution_status": target.execution_status,
        "migration_execution_mode": target.execution_mode,
        "pending_migrations": [],
        "checksum_mismatches": [],
        "relations": relations,
        "row_counts": counts,
        "constraints": constraints,
        "boundaries": {
            "db_writes": 0,
            "provider_calls": 0,
            "gmail_reads": 0,
            "email_actions": 0,
            "application_submission_actions": 0,
            "application_state_mutations": 0,
        },
    }


def validate_report(report: Mapping[str, object], *, phase: str, source_sha: str) -> None:
    if report.get("phase") != phase:
        raise QualificationStop("PHASE_MISMATCH")
    if report.get("source_sha") != source_sha:
        raise QualificationStop("SOURCE_SHA_MISMATCH")
    boundaries = report.get("boundaries")
    if not isinstance(boundaries, Mapping):
        raise QualificationStop("BOUNDARIES_MISSING")
    for key in (
        "db_writes",
        "provider_calls",
        "gmail_reads",
        "email_actions",
        "application_submission_actions",
        "application_state_mutations",
    ):
        if boundaries.get(key) != 0:
            raise QualificationStop(f"BOUNDARY_NOT_ZERO:{key}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("preflight", "postapply"))
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = (
        preflight(source_sha=args.source_sha)
        if args.phase == "preflight"
        else postapply(source_sha=args.source_sha)
    )
    validate_report(report, phase=args.phase, source_sha=args.source_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(f"F5_SCHEMA_PHASE={args.phase}")
    print(f"F5_SCHEMA_SOURCE_SHA={args.source_sha}")
    print(f"F5_SCHEMA_TARGET={TARGET_MIGRATION}")
    if args.phase == "preflight":
        print("F5_SCHEMA_CHECKSUM_DRIFT=0")
        print(f"F5_SCHEMA_PENDING={TARGET_MIGRATION}")
        print("F5_SCHEMA_TARGET_RELATIONS_PRESENT=0")
    else:
        counts = report["row_counts"]
        print("F5_SCHEMA_CHECKSUM_DRIFT=0")
        print("F5_SCHEMA_PENDING=0")
        print("F5_SCHEMA_RELATIONS=PASS")
        print(f"F5_SCHEMA_ROW_COUNTS={json.dumps(counts, sort_keys=True)}")
    print("F5_SCHEMA_READ_ONLY_PROOF=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
