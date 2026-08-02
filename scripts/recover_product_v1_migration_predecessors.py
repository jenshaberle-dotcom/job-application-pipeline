"""Preflight or recover the known Product V1 predecessor migration gaps.

This runner handles only migrations 066, 069 and 076. Migration 069 is the
idempotent repair/superset of 066, so the recovery executes 069 and records 066
as bootstrapped when 066 is not already complete. Migration 076 is then applied
normally. Any other unresolved migration below 077 blocks the recovery.

Default execution is read-only. No source, provider, scheduler or application
workflow is invoked by this script.
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


BASE_TAXONOMY_KEY = "066_harden_origin_pattern_promotion_taxonomy.sql"
REPAIR_TAXONOMY_KEY = "069_repair_origin_observed_pattern_taxonomy_columns.sql"
PROFILE_REBASELINE_KEY = "076_rebaseline_stepstone_ml_data_search_profile.sql"
RECOVERY_MIGRATION_KEYS = (
    BASE_TAXONOMY_KEY,
    REPAIR_TAXONOMY_KEY,
    PROFILE_REBASELINE_KEY,
)
RECOVERY_APPROVAL_TOKEN = "recover_product_v1_predecessors_066_069_076"
SUCCESS_STATUSES = {"success", "bootstrapped"}


def _migration_map(migrations: Sequence[MigrationFile]) -> dict[str, MigrationFile]:
    return {migration.migration_key: migration for migration in migrations}


def recovery_migrations(migrations: Sequence[MigrationFile]) -> dict[str, MigrationFile]:
    by_key = _migration_map(migrations)
    missing = [key for key in RECOVERY_MIGRATION_KEYS if key not in by_key]
    if missing:
        raise RuntimeError(f"Missing recovery migration file(s): {missing}")
    return {key: by_key[key] for key in RECOVERY_MIGRATION_KEYS}


def migration_is_complete(
    migration: MigrationFile,
    tracked: dict[str, TrackedMigration],
) -> bool:
    existing = tracked.get(migration.migration_key)
    return bool(existing and existing.execution_status in SUCCESS_STATUSES)


def unexpected_unresolved_predecessors(
    migrations: Sequence[MigrationFile],
    tracked: dict[str, TrackedMigration],
) -> list[MigrationFile]:
    allowed = set(RECOVERY_MIGRATION_KEYS)
    return [
        migration
        for migration in migrations
        if migration.version_number < 77
        and migration.migration_key not in allowed
        and not migration_is_complete(migration, tracked)
    ]


def print_preflight(
    *,
    migrations: Sequence[MigrationFile],
    tracked: dict[str, TrackedMigration],
) -> None:
    targets = recovery_migrations(migrations)
    unexpected = unexpected_unresolved_predecessors(migrations, tracked)

    print("Product V1 predecessor recovery preflight")
    print("mode: read_only")
    for key in RECOVERY_MIGRATION_KEYS:
        existing = tracked.get(key)
        status = existing.execution_status if existing else "pending"
        print(f"- {key}: {status}")
    print("recovery_plan:")
    print("- execute 069 as the idempotent repair/superset of 066 when needed")
    print("- record unresolved 066 as bootstrapped only after 069 succeeds")
    print("- execute 076 normally when needed")
    print(f"unexpected_unresolved_predecessors: {len(unexpected)}")
    if unexpected:
        print("blocked: additional unresolved migrations below version 077")
        for migration in unexpected:
            print(f"- {migration.migration_key}")
    else:
        pending = [
            key
            for key, migration in targets.items()
            if not migration_is_complete(migration, tracked)
        ]
        print(f"recovery_actions_required: {len(pending)}")
        print("ready_for_operator_apply: true")
    print("boundaries:")
    print("- no StepStone call")
    print("- no provider call")
    print("- no source activation")
    print("- no scheduler mutation")
    print("- no application generation or submission")


def apply_recovery(
    *,
    migrations: Sequence[MigrationFile],
    tracked: dict[str, TrackedMigration],
    applied_by: str,
) -> tuple[str, ...]:
    targets = recovery_migrations(migrations)
    unexpected = unexpected_unresolved_predecessors(migrations, tracked)
    if unexpected:
        names = ", ".join(item.migration_key for item in unexpected)
        raise RuntimeError(
            "Cannot recover Product V1 predecessors while additional unresolved "
            "migration(s) exist below version 077: " + names
        )

    base = targets[BASE_TAXONOMY_KEY]
    repair = targets[REPAIR_TAXONOMY_KEY]
    profile = targets[PROFILE_REBASELINE_KEY]
    actions: list[str] = []

    with connect() as conn:
        if not schema_migrations_exists(conn):
            raise RuntimeError(
                "schema_migrations table does not exist; migration tracking must be restored first"
            )
        with conn.transaction():
            current = load_tracked_migrations(conn)

            if not migration_is_complete(repair, current):
                with conn.cursor() as cur:
                    cur.execute(repair.path.read_text(encoding="utf-8"))
                insert_tracking_row(
                    conn,
                    repair,
                    execution_status="success",
                    execution_mode="script_apply",
                    applied_by=applied_by,
                )
                actions.append(f"applied:{repair.migration_key}")

            if not migration_is_complete(base, current):
                insert_tracking_row(
                    conn,
                    base,
                    execution_status="bootstrapped",
                    execution_mode="manual_bootstrap",
                    applied_by=applied_by,
                )
                actions.append(
                    f"bootstrapped:{base.migration_key}:superseded_by_069"
                )

            if not migration_is_complete(profile, current):
                with conn.cursor() as cur:
                    cur.execute(profile.path.read_text(encoding="utf-8"))
                insert_tracking_row(
                    conn,
                    profile,
                    execution_status="success",
                    execution_mode="script_apply",
                    applied_by=applied_by,
                )
                actions.append(f"applied:{profile.migration_key}")

    return tuple(actions)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
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

    if args.approval_token != RECOVERY_APPROVAL_TOKEN:
        raise SystemExit(
            f"Exact approval token required: {RECOVERY_APPROVAL_TOKEN}"
        )

    actions = apply_recovery(
        migrations=migrations,
        tracked=tracked,
        applied_by=args.applied_by,
    )
    print(f"predecessor_recovery_actions: {len(actions)}")
    for action in actions:
        print(f"- {action}")
    print("next: run the Product V1 migration preflight for 077 and 078")


if __name__ == "__main__":
    main()
