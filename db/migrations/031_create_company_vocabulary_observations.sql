
-- S5G-A Company Vocabulary Foundation
-- Company vocabulary observations are learning evidence, not Bronze jobs, not source activation,
-- not connector registration, not scheduler changes, and not search-profile mutations.

CREATE TABLE IF NOT EXISTS company_vocabulary_observations (
    id BIGSERIAL PRIMARY KEY,
    company_key TEXT NOT NULL,
    company_name TEXT,
    observed_term TEXT NOT NULL,
    source_name TEXT NOT NULL,
    evidence_type TEXT NOT NULL DEFAULT 'market_evidence_title',
    observation_count INTEGER NOT NULL DEFAULT 1,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by TEXT NOT NULL DEFAULT 'agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_company_vocabulary_observation_count_non_negative CHECK (observation_count >= 0),
    CONSTRAINT chk_company_vocabulary_term_not_blank CHECK (length(trim(observed_term)) > 0),
    UNIQUE (company_key, observed_term, source_name, evidence_type)
);

CREATE INDEX IF NOT EXISTS idx_company_vocabulary_company_term
    ON company_vocabulary_observations (company_key, observed_term);

CREATE INDEX IF NOT EXISTS idx_company_vocabulary_term_count
    ON company_vocabulary_observations (observed_term, observation_count DESC, last_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_company_vocabulary_source_seen
    ON company_vocabulary_observations (source_name, last_seen_at DESC);
