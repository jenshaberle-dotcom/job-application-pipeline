# DB Migration Tracking Foundation

## Purpose

S7Y introduces DB-backed migration tracking so local, CI and future cloud environments can answer which migration files were applied and whether their file checksums still match the tracked state.

## Why now

The project has passed migration `053`, includes manually applied local migrations and is preparing more controlled source-candidate flows. At this point, checking migration state only through memory or ad hoc SQL target-state checks is no longer sufficient.

## Table

`schema_migrations` stores:

- migration key / filename
- version number for ordering
- SHA-256 checksum
- execution status
- execution mode
- applied timestamp
- applied by
- error message for failed script-applied migrations

The filename is the primary identity. The numeric prefix is intentionally not unique because older project migrations have historical numbering irregularities.

## Commands

Check tracking state:

`python -m scripts.apply_db_migrations --status`

Bootstrap already-applied local migrations after the tracking table exists:

`python -m scripts.apply_db_migrations --bootstrap-existing --applied-by jens`

Apply future pending migrations:

`python -m scripts.apply_db_migrations --apply --applied-by jens`

## Boundary

This foundation does not migrate existing data by itself. It creates migration tracking and provides a controlled way to bootstrap and apply migrations from the repository. It does not use CSV/Excel/export artifacts as inputs.
