-- S7Y DB migration tracking foundation.
--
-- Purpose:
--   Create a DB-backed migration tracking table before additional source
--   candidates are moved through the controlled activation chain.
--
-- Design notes:
-- - migration_key / filename is the primary identity because this repository
--   has historical migration-number irregularities documented in ADR-018.
-- - version_number is stored for ordering and review, but it is intentionally
--   not unique.
-- - checksum_sha256 records the current file checksum at tracking/apply time.
--
-- Boundary:
-- - This migration only creates the tracking table and indexes.
-- - It does not mark existing migrations as applied.
-- - It does not run other migrations.
-- - It does not modify pipeline data.
-- - It does not use CSV/Excel/export artifacts as inputs.

CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_key TEXT PRIMARY KEY,
    version_number INTEGER NOT NULL,
    filename TEXT NOT NULL UNIQUE,
    checksum_sha256 TEXT NOT NULL,
    execution_status TEXT NOT NULL,
    execution_mode TEXT NOT NULL,
    applied_by TEXT,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_schema_migrations_execution_status
        CHECK (execution_status IN ('bootstrapped', 'success', 'failed')),
    CONSTRAINT chk_schema_migrations_execution_mode
        CHECK (execution_mode IN ('manual_bootstrap', 'script_apply', 'manual_tracking_migration')),
    CONSTRAINT chk_schema_migrations_checksum_sha256
        CHECK (checksum_sha256 ~ '^[a-f0-9]{64}$')
);

CREATE INDEX IF NOT EXISTS idx_schema_migrations_version_number
    ON schema_migrations (version_number, filename);

CREATE INDEX IF NOT EXISTS idx_schema_migrations_execution_status
    ON schema_migrations (execution_status);

COMMENT ON TABLE schema_migrations IS
    'DB-backed migration tracking for local/cloud reproducibility.';

COMMENT ON COLUMN schema_migrations.migration_key IS
    'Stable migration identity. Uses filename to tolerate historical duplicate version numbers.';

COMMENT ON COLUMN schema_migrations.version_number IS
    'Numeric prefix used for ordering only; intentionally not unique.';
