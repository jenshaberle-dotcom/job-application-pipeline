"""Preflight or atomically apply Product V1 migrations 077 and 078.

Default execution is read-only. Applying the reviewed migrations requires both
``--apply`` and the exact approval token. No source, provider, scheduler or
application workflow is invoked by this script.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence

from scripts.apply_db_migrations import (
    MigrationFile,
    TrackedMigration,
    connect,
    discover_migration_files,
    ensure_no_checksum_mismatches,
    insert_tracking_row,
    load_tracked_migrations,
    schema_migrations_exists,
)


TARGET_MIGRATION_KEYS = (
    "077_create_product_v1_monolith_foundation.sql",
    "078_activate_product_v1_operator_policy.sql",
)
APPLY_APPROVAL_TOKEN = "apply_product_v1_runtime_migrations_077_078"
SUCCESS_STATUSES = {"success", "bootstrapped"}


def _migration_map(migrations: Sequence[MigrationFile]) -> dict[str, MigrationFile]:
    return {migration.migration_key: migration for migration in migrations}


def target_migrations(migrations: Sequence[MigrationFile]) -> list[MigrationFile]:
    by_key = _migration_map(migrations)
    missing = [key for key in TARGET_MIGRATION_KEYS if key not in by_key]
    if missing:
        raise RuntimeError(f"Missing target migration file(s): {missing}")
    return [by_key[key] for key in TARGET_MIGRATION_KEYS]


def migration_is_complete(
    migration: MigrationFile,
    tracked: dict[str, TrackedMigration],
) -> bool:
    existing = tracked.get(migration.migration_key)
    return bool(existing and existing.execution_status in SUCCESS_STATUSES)


def unresolved_predecessors(
    migrations: Sequence[MigrationFile],
    tracked: dict[str, TrackedMigration],
) -> list[MigrationFile]:
    return [
        migration
        for migration in migrations
        if migration.version_number < 77
        and not migration_is_complete(migration, tracked)
    ]


def print_preflight(
    *,
    migrations: Sequence[MigrationFile],
    tracked: dict[str, TrackedMigration],
) -> None:
    targets = target_migrations(migrations)
    predecessors = unresolved_predecessors(migrations, tracked)

    print("Product V1 runtime migration preflight")
    print("mode: read_only")
    print(f"target_migrations: {len(targets)}")
    print(f"unresolved_predecessors: {len(predecessors)}")
    for migration in targets:
        existing = tracked.get(migration.migration_key)
        status = existing.execution_status if existing else "pending"
        print(f"- {migration.migration_key}: {status}")
    if predecessors:
        print("blocked: unresolved migrations below version 077")
        for migration in predecessors:
            print(f"- {migration.migration_key}")
    else:
        print("ready_for_operator_apply: true")
    print("boundaries:")
    print("- no StepStone call")
    print("- no provider call")
    print("- no source activation")
    print("- no scheduler mutation")
    print("- no application generation or submission")
    print("- current compensation remains local runtime context only")


def apply_targets(
    *,
    migrations: Sequence[MigrationFile],
    tracked: dict[str, TrackedMigration],
    applied_by: str,
) -> int:
    targets = target_migrations(migrations)
    predecessors = unresolved_predecessors(migrations, tracked)
    if predecessors:
        names = ", ".join(item.migration_key for item in predecessors)
        raise RuntimeError(
            "Cannot apply Product V1 migrations before unresolved predecessor(s): "
            + names
        )

    pending_targets = [
        migration
        for migration in targets
        if not migration_is_complete(migration, tracked)
    ]
    if not pending_targets:
        return 0

    with connect() as conn:
        if not schema_migrations_exists(conn):
            raise RuntimeError(
                "schema_migrations table does not exist; migration tracking must be restored first"
            )
        with conn.transaction():
            for migration in pending_targets:
                sql = migration.path.read_text(encoding="utf-8")
                with conn.cursor() as cur:
                    cur.execute(sql)
                insert_tracking_row(
                    conn,
                    migration,
                    execution_status="success",
                    execution_mode="product_v1_atomic_apply",
                    applied_by=applied_by,
                )
    return len(pending_targets)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply only migrations 077 and 078 in one transaction.",
    )
    parser.add_argument("--approval-token")
    parser.add_argument("--applied-by", default="jens")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    migrations = discover_migration_files()

    with connect() as conn:
        if not schema_migrations_exists(conn):
            raise SystemExit(
                "schema_migrations table is missing; run the normal migration-recovery procedure first"
            )
        tracked = load_tracked_migrations(conn)

    ensure_no_checksum_mismatches(migrations, tracked)

    if not args.apply:
        print_preflight(migrations=migrations, tracked=tracked)
        return

    if args.approval_token != APPLY_APPROVAL_TOKEN:
        raise SystemExit(
            f"Exact approval token required: {APPLY_APPROVAL_TOKEN}"
        )

    applied = apply_targets(
        migrations=migrations,
        tracked=tracked,
        applied_by=args.applied_by,
    )
    print(f"applied_product_v1_migrations: {applied}")
    print("next: run this command again without --apply to verify tracked state")


if __name__ == "__main__":
    main()
