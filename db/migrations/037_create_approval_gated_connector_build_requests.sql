-- S6C Approval-Gated Connector Build Agent Foundation
--
-- Purpose:
--   Store DB-backed connector artifact build requests after Search Intelligence
--   and employer-origin gate evidence indicate that a candidate should move
--   from unresolved evidence into a reviewable connector implementation path.
--
-- Boundary:
--   - no auto-PR creation
--   - no connector registration approval
--   - no source activation
--   - no Bronze writes
--   - no recurring ingestion or scheduler change
--   - no CSV/Excel/export artifact as pipeline input
--   - explicit build approval is required before writing connector artifacts

ALTER TABLE employer_origin_connector_generation_plans
    DROP CONSTRAINT IF EXISTS chk_employer_origin_connector_generation_status;

ALTER TABLE employer_origin_connector_generation_plans
    ADD CONSTRAINT chk_employer_origin_connector_generation_status CHECK (
        generation_status = ANY (ARRAY[
            'ready'::text,
            'already_generated'::text,
            'gate_reassessment_required'::text,
            'manual_review_required'::text,
            'blocked'::text,
            'not_applicable'::text
        ])
    );

ALTER TABLE employer_origin_connector_generation_plans
    DROP CONSTRAINT IF EXISTS chk_employer_origin_connector_generation_recommendation;

ALTER TABLE employer_origin_connector_generation_plans
    ADD CONSTRAINT chk_employer_origin_connector_generation_recommendation CHECK (
        recommendation = ANY (ARRAY[
            'prepare_connector_artifact_dry_run'::text,
            'review_existing_connector_artifacts'::text,
            'rerun_employer_origin_gate_reassessment'::text,
            'stop_before_connector_generation'::text,
            'monitor_existing_source'::text
        ])
    );

CREATE TABLE IF NOT EXISTS employer_origin_connector_build_requests (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT NOT NULL
        REFERENCES employer_origin_source_candidates (id)
        ON DELETE CASCADE,
    build_status TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    build_mode TEXT NOT NULL,
    source_name_candidate TEXT NOT NULL,
    source_type_candidate TEXT NOT NULL,
    connector_module_path TEXT,
    connector_test_path TEXT,
    connector_docs_path TEXT,
    next_command TEXT,
    build_request JSONB NOT NULL DEFAULT '{}'::jsonb,
    boundary JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by TEXT NOT NULL DEFAULT 'agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (candidate_id),
    CONSTRAINT chk_employer_origin_connector_build_status CHECK (
        build_status = ANY (ARRAY[
            'build_approval_required'::text,
            'artifact_generation_allowed'::text,
            'artifacts_present'::text,
            'gate_reassessment_required'::text,
            'manual_review_required'::text,
            'blocked'::text,
            'not_applicable'::text
        ])
    ),
    CONSTRAINT chk_employer_origin_connector_build_recommendation CHECK (
        recommendation = ANY (ARRAY[
            'request_explicit_build_approval'::text,
            'generate_connector_artifacts'::text,
            'run_connector_validation'::text,
            'rerun_employer_origin_gate_reassessment'::text,
            'stop_before_build'::text,
            'monitor_existing_source'::text
        ])
    ),
    CONSTRAINT chk_employer_origin_connector_build_mode CHECK (
        build_mode = ANY (ARRAY[
            'none'::text,
            'connector_candidate_from_gate_evidence'::text,
            'bounded_investigation_connector'::text,
            'existing_artifacts'::text
        ])
    )
);

CREATE INDEX IF NOT EXISTS idx_employer_origin_connector_build_status
    ON employer_origin_connector_build_requests (build_status, recommendation, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_employer_origin_connector_build_source
    ON employer_origin_connector_build_requests (source_name_candidate, source_type_candidate);
