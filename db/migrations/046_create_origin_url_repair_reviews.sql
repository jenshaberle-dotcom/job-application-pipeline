-- S7P Reviewed Origin URL Repair Application
--
--
-- Boundary:
--   no_connector_artifact_generation
--   no_connector_registration
--   no_source_activation
--   no_bronze_write
--   no_scheduler_change
-- Purpose:
--   Persist reviewed URL-repair decisions that are derived from S7N connector
--   feasibility feedback and surfaced through the S7O connector build candidate
--   queue. This closes the harmless repair loop for cases such as a stale
--   .jsp career URL that has a concrete .html repair candidate.
--
-- Boundary:
--   - no connector artifact generation
--   - no connector registration
--   - no source activation
--   - no Bronze writes
--   - no scheduler changes
--   - no automatic candidate promotion or approval-gate bypass
--   - no CSV/Excel/export artifact as pipeline input

CREATE TABLE IF NOT EXISTS employer_origin_url_repair_reviews (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT NOT NULL
        REFERENCES employer_origin_source_candidates(id)
        ON DELETE CASCADE,
    feasibility_review_id BIGINT
        REFERENCES connector_feasibility_reviews(id)
        ON DELETE SET NULL,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    previous_candidate_url TEXT,
    repair_candidate_url TEXT NOT NULL,
    normalized_repair_url TEXT,
    selected_source_type TEXT,
    repair_status TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    boundary JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by TEXT NOT NULL DEFAULT 'agent',
    applied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_employer_origin_url_repair_status CHECK (
        repair_status = ANY (ARRAY[
            'repair_recommended'::text,
            'repair_applied'::text,
            'manual_review_required'::text,
            'not_applicable'::text
        ])
    ),
    CONSTRAINT chk_employer_origin_url_repair_decision CHECK (
        decision = ANY (ARRAY[
            'apply_repair_candidate_url'::text,
            'manual_review_required'::text,
            'abort_documented'::text,
            'no_action'::text
        ])
    ),
    CONSTRAINT chk_employer_origin_url_repair_applied_has_url CHECK (
        repair_status <> 'repair_applied'
        OR normalized_repair_url IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_employer_origin_url_repair_reviews_candidate
    ON employer_origin_url_repair_reviews(candidate_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_employer_origin_url_repair_reviews_status
    ON employer_origin_url_repair_reviews(repair_status, created_at DESC);

CREATE OR REPLACE VIEW gold_origin_url_repair_review_history AS
SELECT
    r.id AS repair_review_id,
    r.candidate_id,
    r.company_key,
    r.company_name,
    r.previous_candidate_url,
    r.repair_candidate_url,
    r.normalized_repair_url,
    r.selected_source_type,
    r.repair_status,
    r.decision,
    r.reason,
    r.reviewed_by,
    r.applied_at,
    r.created_at,
    c.status AS candidate_status,
    c.candidate_url AS current_candidate_url,
    r.feasibility_review_id
FROM employer_origin_url_repair_reviews r
JOIN employer_origin_source_candidates c ON c.id = r.candidate_id;
