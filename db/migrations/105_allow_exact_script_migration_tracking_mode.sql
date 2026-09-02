-- S7Y / DEMO-001 migration tracking contract repair.
--
-- `scripts.apply_db_migrations --apply-exact` intentionally records an exact
-- guarded script execution as `script_apply_exact`. Migration 054 predates that
-- runner mode and therefore rejects otherwise-successful exact applies at the
-- tracking insert. Extend only the tracking vocabulary; do not alter migration
-- status semantics, product data, ranking, sources, applications, or providers.

ALTER TABLE schema_migrations
DROP CONSTRAINT IF EXISTS chk_schema_migrations_execution_mode;

ALTER TABLE schema_migrations
ADD CONSTRAINT chk_schema_migrations_execution_mode
CHECK (
    execution_mode IN (
        'manual_bootstrap',
        'script_apply',
        'script_apply_exact',
        'manual_tracking_migration'
    )
);
