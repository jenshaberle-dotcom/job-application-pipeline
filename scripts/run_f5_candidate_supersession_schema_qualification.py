"""Read-only qualification for F5 candidate source-identity migration 114."""
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

TARGET_MIGRATION = "114_application_event_candidate_source_identity.sql"
PREREQUISITE_MIGRATION = "113_enable_mailbox_first_application_tracking.sql"
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


def _constraint_names(conn: Any) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = 'public.application_event_candidates'::regclass
            """
        )
        return {str(row["conname"]) for row in cur.fetchall()}


def _index_definitions(conn: Any) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'application_event_candidates'
            """
        )
        return {str(row["indexname"]): str(row["indexdef"]) for row in cur.fetchall()}


def _view_definition(conn: Any) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_get_viewdef(%s::regclass, true) AS definition", (TARGET_VIEW,))
        row = cur.fetchone()
    return str(row["definition"] if row else "")


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


def _migration_truth(conn: Any):
    migrations = discover_migration_files()
    tracked = load_tracked_migrations(conn)
    mismatches = checksum_mismatches(migrations, tracked)
    pending = pending_migrations(migrations, tracked)
    return migrations, tracked, mismatches, pending


def preflight(*, source_sha: str) -> dict[str, object]:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        if not schema_migrations_exists(conn):
            raise QualificationStop("SCHEMA_MIGRATIONS_MISSING")
        migrations, tracked, mismatches, pending = _migration_truth(conn)
        target, state = select_exact_pending_migration(
            migrations=migrations,
            tracked=tracked,
            migration_key=TARGET_MIGRATION,
            require_sole_pending=True,
        )
        prerequisite = tracked.get(PREREQUISITE_MIGRATION)
        columns = _column_inventory(conn, "application_event_candidates")
        constraints = _constraint_names(conn)
        counts = _counts(conn)

    if mismatches:
        raise QualificationStop("CHECKSUM_DRIFT")
    if prerequisite is None or prerequisite.execution_status != "success":
        raise QualificationStop("PREREQUISITE_113_NOT_SUCCESS")
    pending_keys = [item.migration_key for item in pending]
    if state != "pending" or pending_keys != [TARGET_MIGRATION]:
        raise QualificationStop(f"PENDING_SET_MISMATCH:{pending_keys}:{state}")
    for column in ("source_identity_key", "is_active", "supersedes_candidate_id"):
        if column in columns:
            raise QualificationStop(f"PRESTATE_COLUMN_ALREADY_PRESENT:{column}")
    if "uq_application_event_candidate_evidence" not in constraints:
        raise QualificationStop("PRESTATE_OLD_INTERPRETATION_UNIQUE_MISSING")

    return {
        "schema": "jap.f5.candidate_supersession_schema_qualification.v1",
        "phase": "preflight",
        "source_sha": source_sha,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "target_migration": TARGET_MIGRATION,
        "target_version": target.version_number,
        "target_checksum_sha256": target.checksum_sha256,
        "pending_migrations": pending_keys,
        "checksum_mismatches": [],
        "candidate_row_count": counts["application_event_candidates"],
        "row_counts": counts,
        "boundaries": {
            "db_writes": 0,
            "gmail_reads": 0,
            "email_actions": 0,
            "application_submission_actions": 0,
            "authoritative_state_mutations": 0,
        },
    }


def _applied(*, source_sha: str, phase: str) -> dict[str, object]:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        if not schema_migrations_exists(conn):
            raise QualificationStop("SCHEMA_MIGRATIONS_MISSING")
        _, tracked, mismatches, pending = _migration_truth(conn)
        columns = _column_inventory(conn, "application_event_candidates")
        constraints = _constraint_names(conn)
        indexes = _index_definitions(conn)
        view_definition = _view_definition(conn)
        counts = _counts(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*)::integer AS count
                FROM (
                    SELECT source_kind, source_identity_key
                    FROM application_event_candidates
                    WHERE is_active
                    GROUP BY source_kind, source_identity_key
                    HAVING count(*) > 1
                ) duplicate_active
                """
            )
            duplicate_active = int(cur.fetchone()["count"])

    if mismatches:
        raise QualificationStop("CHECKSUM_DRIFT")
    target = tracked.get(TARGET_MIGRATION)
    if target is None or target.execution_status != "success":
        raise QualificationStop("TARGET_MIGRATION_NOT_SUCCESS")
    if pending:
        raise QualificationStop(
            "UNEXPECTED_PENDING:" + ",".join(item.migration_key for item in pending)
        )
    if columns.get("source_identity_key", {}).get("is_nullable") != "NO":
        raise QualificationStop("SOURCE_IDENTITY_MISSING_OR_NULLABLE")
    if columns.get("is_active", {}).get("is_nullable") != "NO":
        raise QualificationStop("IS_ACTIVE_MISSING_OR_NULLABLE")
    if "supersedes_candidate_id" not in columns:
        raise QualificationStop("SUPERSEDES_COLUMN_MISSING")
    if "uq_application_event_candidate_evidence" in constraints:
        raise QualificationStop("OLD_INTERPRETATION_UNIQUE_STILL_PRESENT")
    required_constraints = {
        "chk_application_event_candidate_source_identity_nonempty",
        "chk_application_event_candidate_no_self_supersede",
        "fk_application_event_candidate_supersedes_same_source",
    }
    missing_constraints = sorted(required_constraints - constraints)
    if missing_constraints:
        raise QualificationStop("CONSTRAINTS_MISSING:" + ",".join(missing_constraints))
    active_index = indexes.get("uq_application_event_candidate_active_source", "")
    active_index_upper = active_index.upper()
    if (
        "CREATE UNIQUE INDEX" not in active_index_upper
        or "WHERE" not in active_index_upper
        or "IS_ACTIVE" not in active_index_upper
    ):
        raise QualificationStop("ACTIVE_SOURCE_UNIQUE_INDEX_INVALID")
    if duplicate_active != 0:
        raise QualificationStop(f"DUPLICATE_ACTIVE_SOURCE_IDENTITIES:{duplicate_active}")
    if view_definition.count("is_active") < 2:
        raise QualificationStop("TRACKING_VIEW_DOES_NOT_FILTER_SUPERSEDED_EVIDENCE")

    return {
        "schema": "jap.f5.candidate_supersession_schema_qualification.v1",
        "phase": phase,
        "source_sha": source_sha,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "target_migration": TARGET_MIGRATION,
        "pending_migrations": [],
        "checksum_mismatches": [],
        "candidate_row_count": counts["application_event_candidates"],
        "duplicate_active_source_identities": duplicate_active,
        "row_counts": counts,
        "boundaries": {
            "db_writes": 0,
            "gmail_reads": 0,
            "email_actions": 0,
            "application_submission_actions": 0,
            "authoritative_state_mutations": 0,
        },
    }


def postapply(*, source_sha: str) -> dict[str, object]:
    return _applied(source_sha=source_sha, phase="postapply")


def current(*, source_sha: str) -> dict[str, object]:
    return _applied(source_sha=source_sha, phase="current")


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
    parser.add_argument("--phase", required=True, choices=("preflight", "postapply", "current"))
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    runner = {"preflight": preflight, "postapply": postapply, "current": current}[args.phase]
    report = runner(source_sha=args.source_sha)
    validate_report(report, phase=args.phase, source_sha=args.source_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"F5_CANDIDATE_SUPERSESSION_SCHEMA_PHASE={args.phase}")
    print(f"F5_CANDIDATE_SUPERSESSION_SCHEMA_SOURCE={args.source_sha}")
    print(f"F5_CANDIDATE_SUPERSESSION_SCHEMA_TARGET={TARGET_MIGRATION}")
    print("F5_CANDIDATE_SUPERSESSION_SCHEMA_READ_ONLY_PROOF=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
