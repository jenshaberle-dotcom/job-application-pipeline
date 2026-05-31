-- S5C/D Search Intelligence Learning Loop
-- Tracks validation outcomes for suggested search terms and derives confidence snapshots.
-- This is review/learning state only: no automatic search-profile mutation, no source activation,
-- no connector registration, no scheduler change and no Bronze persistence.

CREATE TABLE IF NOT EXISTS search_term_validation_runs (
    id BIGSERIAL PRIMARY KEY,
    suggestion_id BIGINT REFERENCES search_term_suggestions(id),
    candidate_id BIGINT NOT NULL REFERENCES employer_origin_source_candidates(id),
    company_key TEXT NOT NULL,
    source_name_candidate TEXT,
    source_family_candidate TEXT,
    suggested_term TEXT NOT NULL,
    validation_scope TEXT NOT NULL DEFAULT 'source_candidate',
    outcome TEXT NOT NULL,
    result_count INTEGER NOT NULL DEFAULT 0,
    relevant_count INTEGER NOT NULL DEFAULT 0,
    noise_count INTEGER NOT NULL DEFAULT 0,
    evidence_url TEXT,
    notes TEXT,
    validated_by TEXT NOT NULL DEFAULT 'agent',
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_search_term_validation_outcome CHECK (
        outcome IN (
            'pending',
            'tested_no_result',
            'tested_found_noise',
            'tested_found_relevant',
            'accepted',
            'rejected'
        )
    ),
    CONSTRAINT chk_search_term_validation_counts CHECK (
        result_count >= 0 AND relevant_count >= 0 AND noise_count >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_search_term_validation_runs_candidate_term
    ON search_term_validation_runs (candidate_id, suggested_term, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_term_validation_runs_outcome_created
    ON search_term_validation_runs (outcome, created_at DESC);

CREATE TABLE IF NOT EXISTS search_term_confidence_snapshots (
    id BIGSERIAL PRIMARY KEY,
    suggested_term TEXT NOT NULL,
    source_family_candidate TEXT,
    validation_scope TEXT NOT NULL DEFAULT 'source_candidate',
    sample_size INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    noise_count INTEGER NOT NULL DEFAULT 0,
    confidence_score NUMERIC(5,2) NOT NULL DEFAULT 0,
    confidence_level TEXT NOT NULL DEFAULT 'unknown',
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by TEXT NOT NULL DEFAULT 'agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_search_term_confidence_level CHECK (
        confidence_level IN ('unknown', 'low', 'medium', 'high')
    )
);

CREATE INDEX IF NOT EXISTS idx_search_term_confidence_snapshots_term_created
    ON search_term_confidence_snapshots (suggested_term, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_term_confidence_snapshots_level_score
    ON search_term_confidence_snapshots (confidence_level, confidence_score DESC, created_at DESC);
