CREATE TABLE IF NOT EXISTS connector_feasibility_reviews (
    id BIGSERIAL PRIMARY KEY,
    scope TEXT NOT NULL DEFAULT 'selected_origin_candidates',
    reviewed_by TEXT NOT NULL,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    likely_feasible_count INTEGER NOT NULL DEFAULT 0,
    manual_review_count INTEGER NOT NULL DEFAULT 0,
    blocked_count INTEGER NOT NULL DEFAULT 0,
    missing_origin_url_count INTEGER NOT NULL DEFAULT 0,
    fetch_enabled BOOLEAN NOT NULL DEFAULT true,
    guardrails JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_connector_feasibility_review_counts CHECK (
        candidate_count >= 0
        AND likely_feasible_count >= 0
        AND manual_review_count >= 0
        AND blocked_count >= 0
        AND missing_origin_url_count >= 0
    )
);

CREATE TABLE IF NOT EXISTS connector_feasibility_review_items (
    id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL REFERENCES connector_feasibility_reviews(id) ON DELETE CASCADE,
    candidate_id BIGINT NOT NULL REFERENCES employer_origin_source_candidates(id) ON DELETE CASCADE,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    origin_url TEXT,
    source_name_candidate TEXT,
    status TEXT,
    risk_level TEXT,
    http_status INTEGER,
    reachable BOOLEAN NOT NULL DEFAULT false,
    page_type TEXT NOT NULL,
    sample_job_count INTEGER NOT NULL DEFAULT 0,
    sample_job_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
    feasibility_status TEXT NOT NULL,
    decision TEXT NOT NULL,
    blocker_code TEXT,
    reason TEXT NOT NULL,
    recommended_next_action TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_connector_feasibility_status CHECK (
        feasibility_status = ANY (ARRAY[
            'likely_feasible',
            'manual_review_required',
            'blocked',
            'missing_origin_url'
        ])
    ),
    CONSTRAINT chk_connector_feasibility_decision CHECK (
        decision = ANY (ARRAY[
            'continue_to_connector_build_planning',
            'manual_review_required',
            'abort_documented',
            'defer_until_origin_url_available'
        ])
    ),
    CONSTRAINT chk_connector_feasibility_counts CHECK (sample_job_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_connector_feasibility_reviews_created
    ON connector_feasibility_reviews (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_connector_feasibility_items_company
    ON connector_feasibility_review_items (company_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_connector_feasibility_items_status
    ON connector_feasibility_review_items (feasibility_status, created_at DESC);

-- S7N quality feedback extension. These ALTER statements keep the migration usable
-- for local databases where the first S7N draft table was already created during review.
ALTER TABLE IF EXISTS connector_feasibility_review_items
    ADD COLUMN IF NOT EXISTS url_quality_status TEXT NOT NULL DEFAULT 'not_evaluated';

ALTER TABLE IF EXISTS connector_feasibility_review_items
    ADD COLUMN IF NOT EXISTS url_quality_feedback_code TEXT;

ALTER TABLE IF EXISTS connector_feasibility_review_items
    ADD COLUMN IF NOT EXISTS url_repair_candidate_url TEXT;

ALTER TABLE IF EXISTS connector_feasibility_review_items
    ADD COLUMN IF NOT EXISTS structural_job_evidence_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE IF EXISTS connector_feasibility_review_items
    ADD CONSTRAINT chk_connector_feasibility_url_quality_status
    CHECK (url_quality_status = ANY (ARRAY[
        'valid_probe_ready'::text,
        'not_reachable'::text,
        'repair_candidate_detected'::text,
        'asset_noise_only'::text,
        'career_page_without_job_structure'::text,
        'unsafe_or_aggregator_url'::text,
        'missing_origin_url'::text,
        'not_evaluated'::text
    ])) NOT VALID;

-- S7N structural evidence quality extension. These ALTER statements keep the
-- migration usable for local review databases where an earlier S7N table draft
-- may already exist.
ALTER TABLE IF EXISTS connector_feasibility_review_items
    ADD COLUMN IF NOT EXISTS url_quality_status TEXT NOT NULL DEFAULT 'not_evaluated';

ALTER TABLE IF EXISTS connector_feasibility_review_items
    ADD COLUMN IF NOT EXISTS url_quality_feedback_code TEXT;

ALTER TABLE IF EXISTS connector_feasibility_review_items
    ADD COLUMN IF NOT EXISTS url_repair_candidate_url TEXT;

ALTER TABLE IF EXISTS connector_feasibility_review_items
    ADD COLUMN IF NOT EXISTS structural_job_evidence_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE IF EXISTS connector_feasibility_review_items
    ADD COLUMN IF NOT EXISTS job_search_page_evidence_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE IF EXISTS connector_feasibility_review_items
    ADD COLUMN IF NOT EXISTS job_detail_candidate_evidence_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE IF EXISTS connector_feasibility_review_items
    ADD COLUMN IF NOT EXISTS career_context_evidence_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE IF EXISTS connector_feasibility_review_items
    ADD COLUMN IF NOT EXISTS rejected_noise_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE IF EXISTS connector_feasibility_review_items
    ADD COLUMN IF NOT EXISTS evidence_classification JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE IF EXISTS connector_feasibility_review_items
    ADD CONSTRAINT chk_connector_feasibility_url_quality_status
    CHECK (url_quality_status = ANY (ARRAY[
        'valid_probe_ready'::text,
        'not_reachable'::text,
        'repair_candidate_detected'::text,
        'asset_noise_only'::text,
        'career_page_without_job_structure'::text,
        'unsafe_or_aggregator_url'::text,
        'missing_origin_url'::text,
        'not_evaluated'::text
    ])) NOT VALID;

