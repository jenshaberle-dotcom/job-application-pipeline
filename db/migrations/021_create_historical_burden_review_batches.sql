-- Create DB-backed review state for historical-burden hot-store removal.
--
-- Generated review artifacts may still be written for humans, but removal review
-- state must live in the database before any production-like or cloud execution.

CREATE TABLE IF NOT EXISTS historical_burden_review_batches (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'proposed',
    review_reason TEXT NOT NULL,
    retention_track TEXT NOT NULL,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    eligible_for_removal_count INTEGER NOT NULL DEFAULT 0,
    blocked_or_non_actionable_count INTEGER NOT NULL DEFAULT 0,
    silver_backed_rows INTEGER NOT NULL DEFAULT 0,
    source_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    burden_category_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    review_status_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_data_bytes BIGINT NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    decision_note TEXT,
    approved_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    CHECK (status IN ('proposed', 'reviewed', 'approved', 'executed', 'cancelled')),
    CHECK (candidate_count >= 0),
    CHECK (eligible_for_removal_count >= 0),
    CHECK (blocked_or_non_actionable_count >= 0),
    CHECK (silver_backed_rows >= 0),
    CHECK (raw_data_bytes >= 0)
);

CREATE TABLE IF NOT EXISTS historical_burden_review_items (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL REFERENCES historical_burden_review_batches(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_job_id BIGINT NOT NULL,
    source_name TEXT NOT NULL,
    external_job_id TEXT,
    source_url TEXT,
    fetched_at TIMESTAMPTZ,
    ingestion_run_id BIGINT,
    search_profile_id BIGINT,
    initial_profile_name TEXT NOT NULL,
    initial_search_term_snapshot TEXT NOT NULL,
    burden_category TEXT NOT NULL,
    retention_track TEXT NOT NULL,
    exists_in_hot_store BOOLEAN NOT NULL DEFAULT true,
    has_silver_job_now BOOLEAN NOT NULL DEFAULT false,
    still_archive_candidate BOOLEAN NOT NULL DEFAULT true,
    eligible_for_future_removal BOOLEAN NOT NULL DEFAULT false,
    review_status TEXT NOT NULL,
    raw_data_bytes BIGINT NOT NULL DEFAULT 0,
    item_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    execution_status TEXT NOT NULL DEFAULT 'not_executed',
    executed_at TIMESTAMPTZ,
    execution_note TEXT,
    CHECK (raw_data_bytes >= 0),
    CHECK (execution_status IN ('not_executed', 'removed_from_hot_store', 'skipped', 'blocked'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_historical_burden_review_items_batch_raw_job
    ON historical_burden_review_items (batch_id, raw_job_id);

CREATE INDEX IF NOT EXISTS idx_historical_burden_review_batches_status
    ON historical_burden_review_batches (status);

CREATE INDEX IF NOT EXISTS idx_historical_burden_review_items_batch_status
    ON historical_burden_review_items (batch_id, review_status);

CREATE INDEX IF NOT EXISTS idx_historical_burden_review_items_source
    ON historical_burden_review_items (source_name);
