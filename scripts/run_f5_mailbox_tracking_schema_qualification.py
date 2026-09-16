"""F5 mailbox-first schema qualification around migration 113.

Preflight proves migration 113 is the sole pending migration with zero checksum
drift and that the currently installed schema still has the expected pre-correction
shape. Post-apply proves the mailbox-first columns/view exist and no application
truth was seeded by the migration.
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

TARGET_MIGRATION = "113_enable_mailbox_first_application_tracking.sql"
TARGET_VIEW = "gold_product_v1_application_tracking"


class QualificationStop(RuntimeError):
    pass


def _column_inventory(conn: Any, relation: str) -> dict[str, dict[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, is_nullable, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
            """,
            (relation,),
        )
        return {
            str(row["column_name"]): {
                "is_nullable": str(row["is_nullable"]),
                "data_type": str(row["data_type"]),
            }
            for row in cur.fetchall()
        }


def _counts(conn: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    with conn.cursor() as cur:
        for relation in (
            "applications",
            "application_submissions",
            "application_lifecycle_events",
            "application_event_candidates",
        ):
            cur.execute(f'SELECT count(*)::integer AS count FROM "{relation}"')
            result[relation] = int(cur.fetchone()["count"])
    return result


def _migration_truth(conn: Any) -> tuple[object, list[object], list[object], dict[str, object]]:
    migrations = discover_migration_files()
    tracked = load_tracked_migrations(conn)
    mismatches = checksum_mismatches(migrations, tracked)
    pending = pending_migrations(migrations, tracked)
    return migrations, mismatches, pending, tracked


def preflight(*, source_sha: str) -> dict[str, object]:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        if not schema_migrations_exists(conn):
            raise QualificationStop("SCHEMA_MIGRATIONS_MISSING")
        migrations, mismatches, pending, tracked = _migration_truth(conn)
        target, state = select_exact_pending_migration(
            migrations=migrations,
            tracked=tracked,
            migration_key=TARGET_MIGRATION,
            require_sole_pending=True,
        )
        applications = _column_inventory(conn, "applications")
        candidates = _column_inventory(conn, "application_event_candidates")
        counts = _counts(conn)

    if mismatches:
        raise QualificationStop("CHECKSUM_DRIFT")
    pending_keys = [item.migration_key for item in pending]
    if state != "pending" or pending_keys != [TARGET_MIGRATION]:
        raise QualificationStop(f"PENDING_SET_MISMATCH:{pending_keys}:{state}")
    if applications.get("silver_job_id", {}).get("is_nullable") != "NO":
        raise QualificationStop("PRESTATE_SILVER_JOB_ALREADY_NULLABLE")
    if "discovery_kind" in applications or "discovered_at" in applications:
        raise QualificationStop("PRESTATE_DISCOVERY_COLUMNS_ALREADY_PRESENT")
    if "observed_at" in candidates:
        raise QualificationStop("PRESTATE_OBSERVED_AT_ALREADY_PRESENT")

    return {
        "schema": "jap.f5.mailbox_first_schema_qualification.v1",
        "phase": "preflight",
        "source_sha": source_sha,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "target_migration": TARGET_MIGRATION,
        "target_version": target.version_number,
        "target_checksum_sha256": target.checksum_sha256,
        "pending_migrations": pending_keys,
        "checksum_mismatches": [],
        "prestate": {
            "applications": applications,
            "application_event_candidates": candidates,
            "row_counts": counts,
        },
        "boundaries": {
            "db_writes": 0,
            "gmail_reads": 0,
            "email_actions": 0,
            "application_submission_actions": 0,
            "authoritative_state_mutations": 0,
        },
    }


def postapply(*, source_sha: str) -> dict[str, object]:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        if not schema_migrations_exists(conn):
            raise QualificationStop("SCHEMA_MIGRATIONS_MISSING")
        _, mismatches, pending, tracked = _migration_truth(conn)
        applications = _column_inventory(conn, "applications")
        candidates = _column_inventory(conn, "application_event_candidates")
        view_columns = _column_inventory(conn, TARGET_VIEW)
        counts = _counts(conn)

    if mismatches:
        raise QualificationStop("CHECKSUM_DRIFT")
    target = tracked.get(TARGET_MIGRATION)
    if target is None or target.execution_status != "success":
        raise QualificationStop("TARGET_MIGRATION_NOT_SUCCESS")
    if pending:
        raise QualificationStop(
            "UNEXPECTED_PENDING:" + ",".join(item.migration_key for item in pending)
        )

    for column in ("silver_job_id", "prepared_at", "prepared_by"):
        if applications.get(column, {}).get("is_nullable") != "YES":
            raise QualificationStop(f"COLUMN_NOT_NULLABLE:{column}")
    if applications.get("discovery_kind", {}).get("is_nullable") != "NO":
        raise QualificationStop("DISCOVERY_KIND_MISSING_OR_NULLABLE")
    if applications.get("discovered_at", {}).get("is_nullable") != "NO":
        raise QualificationStop("DISCOVERED_AT_MISSING_OR_NULLABLE")
    if candidates.get("observed_at", {}).get("is_nullable") != "NO":
        raise QualificationStop("OBSERVED_AT_MISSING_OR_NULLABLE")
    for column in (
        "observed_stage",
        "observed_event_class",
        "observed_at",
        "observed_confidence",
        "effective_stage",
        "effective_stage_basis",
    ):
        if column not in view_columns:
            raise QualificationStop(f"TRACKING_VIEW_COLUMN_MISSING:{column}")

    nonzero = {name: count for name, count in counts.items() if count != 0}
    if nonzero:
        raise QualificationStop(f"MIGRATION_SEEDED_APPLICATION_TRUTH:{nonzero}")

    return {
        "schema": "jap.f5.mailbox_first_schema_qualification.v1",
        "phase": "postapply",
        "source_sha": source_sha,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "target_migration": TARGET_MIGRATION,
        "pending_migrations": [],
        "checksum_mismatches": [],
        "applications_columns": applications,
        "candidate_columns": candidates,
        "tracking_view_columns": view_columns,
        "row_counts": counts,
        "boundaries": {
            "db_writes": 0,
            "gmail_reads": 0,
            "email_actions": 0,
            "application_submission_actions": 0,
            "authoritative_state_mutations": 0,
        },
    }


def validate_report(report: Mapping[str, object], *, phase: str, source_sha: str) -> None:
    if report.get("phase") != phase or report.get("source_sha") != source_sha:
        raise QualificationStop("REPORT_IDENTITY_MISMATCH")
    boundaries = report.get("boundaries")
    if not isinstance(boundaries, Mapping):
        raise QualificationStop("BOUNDARIES_MISSING")
    for key in (
        "db_writes",
        "gmail_reads",
        "email_actions",
        "application_submission_actions",
        "authoritative_state_mutations",
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
    print(f"F5_MAILBOX_SCHEMA_PHASE={args.phase}")
    print(f"F5_MAILBOX_SCHEMA_SOURCE={args.source_sha}")
    print(f"F5_MAILBOX_SCHEMA_TARGET={TARGET_MIGRATION}")
    print("F5_MAILBOX_SCHEMA_READ_ONLY_PROOF=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
