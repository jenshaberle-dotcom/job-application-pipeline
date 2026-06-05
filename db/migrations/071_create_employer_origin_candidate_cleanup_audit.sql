-- 071_create_employer_origin_candidate_cleanup_audit.sql
--
-- SI-015: Audited duplicate candidate cleanup support.
--
-- Purpose:
--   Preserve an audit trail before removing duplicate employer-origin candidate
--   artifacts that were created by workflow bugs such as literal "None" URL
--   handling. The cleanup is intentionally explicit and reviewed; it is not an
--   automatic merge mechanism and it does not activate, crawl, ingest, or write
--   Bronze/Silver data.
--
-- Boundary:
-- - No candidate is removed by this migration.
-- - The table stores evidence snapshots so cleanup can be reviewed later even
--   after a duplicate artifact has been removed.
-- - Removed candidate IDs are deliberately not foreign keys because the row may
--   no longer exist after audited cleanup.

CREATE TABLE IF NOT EXISTS employer_origin_candidate_cleanup_audit (
    id BIGSERIAL PRIMARY KEY,
    cleanup_type TEXT NOT NULL,
    company_key TEXT NOT NULL,
    source_name_candidate TEXT NOT NULL,
    kept_candidate_id BIGINT,
    removed_candidate_id BIGINT,
    reviewed_by TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT employer_origin_candidate_cleanup_audit_type_check
        CHECK (cleanup_type IN (
            'duplicate_candidate_removed'
        )),
    CONSTRAINT employer_origin_candidate_cleanup_audit_reason_check
        CHECK (btrim(reason) <> ''),
    CONSTRAINT employer_origin_candidate_cleanup_audit_reviewed_by_check
        CHECK (btrim(reviewed_by) <> '')
);

CREATE INDEX IF NOT EXISTS idx_employer_origin_candidate_cleanup_audit_company
    ON employer_origin_candidate_cleanup_audit (company_key, source_name_candidate, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_employer_origin_candidate_cleanup_audit_removed_candidate
    ON employer_origin_candidate_cleanup_audit (removed_candidate_id, created_at DESC);
