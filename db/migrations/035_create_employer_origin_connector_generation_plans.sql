-- S6A Employer-Origin Connector Generation Foundation
--
-- Purpose:
--   Store DB-backed connector-generation plans for employer-origin source
--   candidates after the connector-candidate and readiness gates have produced
--   enough evidence for a bounded implementation artifact dry run.
--
-- Boundary:
--   - no auto-PR creation
--   - no connector registration approval
--   - no source activation
--   - no Bronze writes
--   - no recurring ingestion or scheduler change
--   - no CSV/Excel/export artifact as pipeline input

CREATE TABLE IF NOT EXISTS employer_origin_connector_generation_plans (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT NOT NULL
        REFERENCES employer_origin_source_candidates (id)
        ON DELETE CASCADE,
    generation_status TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    source_name_candidate TEXT NOT NULL,
    source_type_candidate TEXT NOT NULL,
    connector_module_path TEXT,
    connector_test_path TEXT,
    connector_docs_path TEXT,
    next_command TEXT,
    plan JSONB NOT NULL DEFAULT '{}'::jsonb,
    boundary JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by TEXT NOT NULL DEFAULT 'agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (candidate_id),
    CONSTRAINT chk_employer_origin_connector_generation_status CHECK (
        generation_status = ANY (ARRAY[
            'ready'::text,
            'already_generated'::text,
            'manual_review_required'::text,
            'blocked'::text,
            'not_applicable'::text
        ])
    ),
    CONSTRAINT chk_employer_origin_connector_generation_recommendation CHECK (
        recommendation = ANY (ARRAY[
            'prepare_connector_artifact_dry_run'::text,
            'review_existing_connector_artifacts'::text,
            'stop_before_connector_generation'::text,
            'monitor_existing_source'::text
        ])
    )
);

CREATE INDEX IF NOT EXISTS idx_employer_origin_connector_generation_status
    ON employer_origin_connector_generation_plans (generation_status, recommendation, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_employer_origin_connector_generation_source
    ON employer_origin_connector_generation_plans (source_name_candidate, source_type_candidate);
