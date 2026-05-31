-- S5B Search Term Learning & Reassessment Queue
-- Turns false-negative risk observations into reviewable search-term suggestions and reassessment work items.
-- This is review state only: no source activation, no connector registration, no scheduler change and no automatic search-profile mutation.

CREATE TABLE IF NOT EXISTS search_term_suggestions (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT NOT NULL REFERENCES employer_origin_source_candidates(id),
    company_key TEXT NOT NULL,
    source_name_candidate TEXT,
    source_family_candidate TEXT,
    suggested_term TEXT NOT NULL,
    suggestion_scope TEXT NOT NULL DEFAULT 'source_candidate',
    status TEXT NOT NULL DEFAULT 'proposed',
    risk_level TEXT NOT NULL,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    last_observed_at TIMESTAMPTZ,
    reason TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by TEXT NOT NULL DEFAULT 'agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (candidate_id, suggested_term)
);

CREATE INDEX IF NOT EXISTS idx_search_term_suggestions_candidate_status
    ON search_term_suggestions (candidate_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_term_suggestions_term_status
    ON search_term_suggestions (suggested_term, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS candidate_reassessment_queue (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT NOT NULL REFERENCES employer_origin_source_candidates(id),
    company_key TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    priority INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    trigger_reason TEXT NOT NULL,
    suggested_search_terms TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by TEXT NOT NULL DEFAULT 'agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_candidate_reassessment_queue_open_candidate
    ON candidate_reassessment_queue (candidate_id)
    WHERE status = 'open';

CREATE INDEX IF NOT EXISTS idx_candidate_reassessment_queue_status_priority
    ON candidate_reassessment_queue (status, priority DESC, updated_at DESC);
