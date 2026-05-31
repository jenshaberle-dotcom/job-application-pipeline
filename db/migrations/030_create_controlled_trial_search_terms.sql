-- S5F Controlled Trial Search-Term Application
-- Applies approved/auto-eligible strategy recommendations as bounded trial terms.
-- This is not a permanent search-profile mutation. Trials are scoped, expiring, measurable and rollbackable.

CREATE TABLE IF NOT EXISTS search_strategy_trial_terms (
    id BIGSERIAL PRIMARY KEY,
    recommendation_id BIGINT REFERENCES search_strategy_recommendations(id),
    candidate_id BIGINT REFERENCES employer_origin_source_candidates(id),
    company_key TEXT NOT NULL,
    source_name_candidate TEXT,
    source_family_candidate TEXT,
    suggested_term TEXT NOT NULL,
    trial_status TEXT NOT NULL DEFAULT 'active',
    trial_scope TEXT NOT NULL DEFAULT 'source_candidate',
    autonomy_level TEXT NOT NULL,
    guardrail_decision TEXT NOT NULL,
    trial_started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    trial_expires_at TIMESTAMPTZ NOT NULL,
    max_result_volume INTEGER NOT NULL DEFAULT 25,
    max_noise_rate NUMERIC(5,2) NOT NULL DEFAULT 0.30,
    applied_by TEXT NOT NULL DEFAULT 'agent',
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_search_strategy_trial_terms_status
        CHECK (trial_status IN ('active', 'expired', 'rolled_back', 'promoted', 'cancelled')),
    CONSTRAINT chk_search_strategy_trial_terms_scope
        CHECK (trial_scope IN ('source_candidate', 'source_family', 'search_profile'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_search_strategy_trial_terms_active_unique
    ON search_strategy_trial_terms (company_key, COALESCE(source_family_candidate, ''), suggested_term)
    WHERE trial_status = 'active';

CREATE INDEX IF NOT EXISTS idx_search_strategy_trial_terms_status_expiry
    ON search_strategy_trial_terms (trial_status, trial_expires_at, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_strategy_trial_terms_candidate
    ON search_strategy_trial_terms (candidate_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS search_strategy_trial_outcomes (
    id BIGSERIAL PRIMARY KEY,
    trial_term_id BIGINT NOT NULL REFERENCES search_strategy_trial_terms(id),
    outcome_status TEXT NOT NULL,
    result_count INTEGER NOT NULL DEFAULT 0,
    relevant_count INTEGER NOT NULL DEFAULT 0,
    noise_count INTEGER NOT NULL DEFAULT 0,
    recorded_by TEXT NOT NULL DEFAULT 'agent',
    notes TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_search_strategy_trial_outcomes_status
        CHECK (outcome_status IN ('pending', 'no_result', 'found_relevant', 'found_noise', 'rollback_recommended', 'promotion_candidate'))
);

CREATE INDEX IF NOT EXISTS idx_search_strategy_trial_outcomes_trial_created
    ON search_strategy_trial_outcomes (trial_term_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_strategy_trial_outcomes_status_created
    ON search_strategy_trial_outcomes (outcome_status, created_at DESC);
