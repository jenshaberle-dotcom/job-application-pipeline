-- 075_create_stop_control_evidence_reviews.sql
--
-- GENERIC-008 Stop-Control Evidence Registry.
--
-- Purpose:
--   Store explicit operator-reviewed safe-stop / no-actionable negative-control
--   evidence for the generic pipeline proof gate without using CSV, Excel,
--   Markdown, JSON exports, or any other local file artifact as process input.
--
-- Boundary:
--   - benchmark/control evidence only
--   - no candidate creation
--   - no gate decision
--   - no connector/source activation
--   - no Bronze/Silver/Gold mutation
--   - no scheduler change
--   - no CSV/Excel/export artifact as pipeline input

CREATE TABLE IF NOT EXISTS stop_control_evidence_reviews (
    id BIGSERIAL PRIMARY KEY,
    control_type TEXT NOT NULL,
    required_for_gap_ids TEXT[] NOT NULL,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    review_action TEXT NOT NULL,
    evidence_strength TEXT NOT NULL DEFAULT 'none',
    evidence_summary TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    review_date DATE NOT NULL,
    boundary TEXT NOT NULL DEFAULT 'review_artifact_only_no_candidate_or_gate_write',
    review_status TEXT NOT NULL DEFAULT 'accepted_for_benchmark',
    source_reference TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    safety_boundary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_stop_control_control_type CHECK (
        control_type = ANY (ARRAY[
            'new_clean_no_actionable_negative_control'::text,
            'existing_safe_stop_negative_control'::text
        ])
    ),
    CONSTRAINT chk_stop_control_required_gaps CHECK (
        required_for_gap_ids @> ARRAY[
            'no_actionable_evidence_coverage'::text,
            'negative_control_coverage'::text
        ]
    ),
    CONSTRAINT chk_stop_control_review_action CHECK (
        review_action = ANY (ARRAY[
            'no_useful_external_hint_no_candidate_creation'::text,
            'provider_auth_failed_requires_key_review'::text,
            'probe_error_requires_retry_or_review'::text
        ])
    ),
    CONSTRAINT chk_stop_control_evidence_strength CHECK (
        evidence_strength = ANY (ARRAY[
            'none'::text,
            'provider_blocked'::text,
            'probe_error'::text,
            'safe_stop'::text
        ])
    ),
    CONSTRAINT chk_stop_control_boundary CHECK (
        boundary = 'review_artifact_only_no_candidate_or_gate_write'
    ),
    CONSTRAINT chk_stop_control_review_status CHECK (
        review_status = ANY (ARRAY[
            'accepted_for_benchmark'::text,
            'rejected'::text,
            'superseded'::text
        ])
    ),
    CONSTRAINT chk_stop_control_company_key CHECK (btrim(company_key) <> ''),
    CONSTRAINT chk_stop_control_company_name CHECK (btrim(company_name) <> ''),
    CONSTRAINT chk_stop_control_reviewer CHECK (btrim(reviewer) <> ''),
    CONSTRAINT chk_stop_control_evidence_summary CHECK (
        btrim(evidence_summary) <> ''
        AND lower(btrim(evidence_summary)) NOT LIKE 'describe why no company-origin/detail/provider evidence%'
    )
);

CREATE INDEX IF NOT EXISTS idx_stop_control_evidence_reviews_status_created
    ON stop_control_evidence_reviews(review_status, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_stop_control_evidence_reviews_company
    ON stop_control_evidence_reviews(company_key, created_at DESC, id DESC);

CREATE OR REPLACE VIEW gold_stop_control_evidence_review_history AS
SELECT
    id AS stop_control_evidence_review_id,
    control_type,
    required_for_gap_ids,
    company_key,
    company_name,
    review_action,
    evidence_strength,
    evidence_summary,
    reviewer,
    review_date,
    boundary,
    review_status,
    source_reference,
    evidence,
    safety_boundary,
    created_at
FROM stop_control_evidence_reviews;
