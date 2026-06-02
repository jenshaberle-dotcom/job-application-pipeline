-- S7I Candidate Expansion from Market Observations
-- Turns unregistered market observations into a bounded, reviewable candidate
-- expansion portfolio. This is decision/review state only: no external browsing,
-- no automatic candidate creation, no source activation, no connector
-- registration, no Bronze writes and no scheduler changes.

CREATE TABLE IF NOT EXISTS candidate_expansion_reviews (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT,
    observed_since TIMESTAMPTZ,
    observed_until TIMESTAMPTZ,
    reviewed_by TEXT NOT NULL DEFAULT 'agent',
    review_mode TEXT NOT NULL DEFAULT 'market_observation_expansion',
    total_observation_count INTEGER NOT NULL DEFAULT 0,
    company_count INTEGER NOT NULL DEFAULT 0,
    create_recommended_count INTEGER NOT NULL DEFAULT 0,
    manual_review_count INTEGER NOT NULL DEFAULT 0,
    insufficient_evidence_count INTEGER NOT NULL DEFAULT 0,
    already_known_count INTEGER NOT NULL DEFAULT 0,
    suppressed_count INTEGER NOT NULL DEFAULT 0,
    boundary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_candidate_expansion_review_counts CHECK (
        total_observation_count >= 0
        AND company_count >= 0
        AND create_recommended_count >= 0
        AND manual_review_count >= 0
        AND insufficient_evidence_count >= 0
        AND already_known_count >= 0
        AND suppressed_count >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_candidate_expansion_reviews_created
    ON candidate_expansion_reviews (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_candidate_expansion_reviews_source_created
    ON candidate_expansion_reviews (source_name, created_at DESC);

CREATE TABLE IF NOT EXISTS candidate_expansion_review_items (
    id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL
        REFERENCES candidate_expansion_reviews(id)
        ON DELETE CASCADE,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    source_name TEXT NOT NULL,
    decision TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    distinct_search_term_count INTEGER NOT NULL DEFAULT 0,
    sample_title_count INTEGER NOT NULL DEFAULT 0,
    latest_observed_at TIMESTAMPTZ,
    known_candidate_id BIGINT REFERENCES employer_origin_source_candidates(id) ON DELETE SET NULL,
    known_candidate_status TEXT,
    recommended_next_action TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_candidate_expansion_item_decision CHECK (
        decision IN (
            'create_candidate_recommended',
            'manual_review_required',
            'insufficient_evidence',
            'already_known',
            'active_candidate_monitoring',
            'suppress_as_noise'
        )
    ),
    CONSTRAINT chk_candidate_expansion_item_counts CHECK (
        evidence_count >= 0
        AND distinct_search_term_count >= 0
        AND sample_title_count >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_candidate_expansion_items_review
    ON candidate_expansion_review_items (review_id);

CREATE INDEX IF NOT EXISTS idx_candidate_expansion_items_decision_priority
    ON candidate_expansion_review_items (decision, priority DESC, evidence_count DESC);

CREATE INDEX IF NOT EXISTS idx_candidate_expansion_items_company
    ON candidate_expansion_review_items (company_key, created_at DESC);
