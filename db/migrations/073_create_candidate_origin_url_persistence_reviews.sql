-- 073_create_candidate_origin_url_persistence_reviews.sql
--
-- CAND-001 Validated Origin URL Persistence Gate.
--
-- Purpose:
--   Store reviewed SZ1 candidate_url persistence decisions when a bounded live
--   Origin Source Discovery run has selected a plausible A/B-tier employer-origin
--   URL but the candidate still has no persisted candidate_url.
--
-- Boundary:
--   - no gate writes
--   - no evidence writes
--   - no connector registration
--   - no source activation
--   - no Bronze/Silver writes
--   - no scheduler changes
--   - URL-Finder exports are review context, not source-of-truth inputs

CREATE TABLE IF NOT EXISTS candidate_origin_url_persistence_reviews (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT NOT NULL
        REFERENCES employer_origin_source_candidates(id)
        ON DELETE CASCADE,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    previous_candidate_url TEXT,
    selected_candidate_url TEXT NOT NULL,
    selected_url_source TEXT NOT NULL DEFAULT 'live_url_finder_validation',
    decision TEXT NOT NULL,
    review_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    boundary JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by TEXT NOT NULL DEFAULT 'agent',
    applied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_candidate_origin_url_persistence_decision CHECK (
        decision = ANY (ARRAY[
            'persist_validated_candidate_url'::text,
            'no_action_already_persisted'::text,
            'manual_review_required'::text,
            'manual_review_required_url_conflict'::text,
            'manual_review_required_duplicate_url'::text,
            'no_selected_url'::text,
            'skip_protected_active_controlled'::text
        ])
    ),
    CONSTRAINT chk_candidate_origin_url_persistence_status CHECK (
        review_status = ANY (ARRAY[
            'write_recommended'::text,
            'applied'::text,
            'manual_review_required'::text,
            'no_action'::text,
            'skipped'::text
        ])
    ),
    CONSTRAINT chk_candidate_origin_url_persistence_applied CHECK (
        review_status <> 'applied'
        OR applied_at IS NOT NULL
    ),
    CONSTRAINT chk_candidate_origin_url_persistence_reason CHECK (btrim(reason) <> ''),
    CONSTRAINT chk_candidate_origin_url_persistence_reviewed_by CHECK (btrim(reviewed_by) <> '')
);

CREATE INDEX IF NOT EXISTS idx_candidate_origin_url_persistence_reviews_candidate
    ON candidate_origin_url_persistence_reviews(candidate_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_candidate_origin_url_persistence_reviews_status
    ON candidate_origin_url_persistence_reviews(review_status, created_at DESC);

CREATE OR REPLACE VIEW gold_candidate_origin_url_persistence_review_history AS
SELECT
    r.id AS persistence_review_id,
    r.candidate_id,
    r.company_key,
    r.company_name,
    r.previous_candidate_url,
    r.selected_candidate_url,
    r.selected_url_source,
    r.decision,
    r.review_status,
    r.reason,
    r.reviewed_by,
    r.applied_at,
    r.created_at,
    c.status AS candidate_status,
    c.candidate_url AS current_candidate_url
FROM candidate_origin_url_persistence_reviews r
JOIN employer_origin_source_candidates c ON c.id = r.candidate_id;
