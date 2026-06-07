-- EO-002A3 StepStone Company Discovery Cycle
-- Supports a bounded, reviewable company-discovery loop for StepStone.
-- Companies are temporarily cooled down to reveal other company blocks; they
-- are not permanently blacklisted because known employers may later provide new
-- market signals and search terms.
--
-- Boundary: no detail pages, no pagination, no automatic candidate creation,
-- no connector activation, no Bronze/Silver writes and no scheduler mutation.

CREATE TABLE IF NOT EXISTS search_term_cycle_state (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    search_profile_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    min_interval_days INTEGER NOT NULL DEFAULT 1,
    current_interval_days INTEGER NOT NULL DEFAULT 3,
    max_interval_days INTEGER NOT NULL DEFAULT 14,
    last_run_at TIMESTAMPTZ,
    next_due_at TIMESTAMPTZ,
    last_quality_score NUMERIC(5,2),
    last_new_company_count INTEGER NOT NULL DEFAULT 0,
    last_known_cooldown_hit_count INTEGER NOT NULL DEFAULT 0,
    is_not_exclusion_enabled BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_search_term_cycle_state_scope UNIQUE (source_name, search_profile_name, search_term),
    CONSTRAINT chk_search_term_cycle_intervals CHECK (
        min_interval_days >= 1
        AND current_interval_days >= min_interval_days
        AND max_interval_days >= current_interval_days
    ),
    CONSTRAINT chk_search_term_cycle_quality CHECK (last_quality_score IS NULL OR (last_quality_score >= 0 AND last_quality_score <= 1)),
    CONSTRAINT chk_search_term_cycle_counts CHECK (
        last_new_company_count >= 0
        AND last_known_cooldown_hit_count >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_search_term_cycle_state_due
    ON search_term_cycle_state (source_name, search_profile_name, next_due_at);

CREATE TABLE IF NOT EXISTS company_discovery_cooldowns (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    search_profile_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    cooldown_until TIMESTAMPTZ NOT NULL,
    reason TEXT NOT NULL,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    learned_title_count INTEGER NOT NULL DEFAULT 0,
    created_by_review_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_company_discovery_cooldown_counts CHECK (
        evidence_count >= 0
        AND learned_title_count >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_company_discovery_cooldowns_active
    ON company_discovery_cooldowns (source_name, search_profile_name, search_term, cooldown_until DESC);

CREATE INDEX IF NOT EXISTS idx_company_discovery_cooldowns_company
    ON company_discovery_cooldowns (company_key, created_at DESC);

CREATE TABLE IF NOT EXISTS stepstone_company_discovery_cycle_reviews (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL DEFAULT 'stepstone',
    search_profile_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    base_query TEXT NOT NULL,
    planned_query TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL,
    observed_count INTEGER NOT NULL DEFAULT 0,
    distinct_company_count INTEGER NOT NULL DEFAULT 0,
    known_cooldown_hit_count INTEGER NOT NULL DEFAULT 0,
    new_company_count INTEGER NOT NULL DEFAULT 0,
    relevance_hits INTEGER NOT NULL DEFAULT 0,
    drift_hits INTEGER NOT NULL DEFAULT 0,
    quality_score NUMERIC(5,2) NOT NULL DEFAULT 0,
    recommended_interval_days INTEGER NOT NULL DEFAULT 3,
    reviewed_by TEXT NOT NULL DEFAULT 'agent',
    boundary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_stepstone_company_cycle_action CHECK (
        action IN ('run_baseline_only', 'run_baseline_learning', 'run_fetch_time_company_not_probe')
    ),
    CONSTRAINT chk_stepstone_company_cycle_counts CHECK (
        observed_count >= 0
        AND distinct_company_count >= 0
        AND known_cooldown_hit_count >= 0
        AND new_company_count >= 0
        AND relevance_hits >= 0
        AND drift_hits >= 0
        AND recommended_interval_days >= 1
    ),
    CONSTRAINT chk_stepstone_company_cycle_quality CHECK (quality_score >= 0 AND quality_score <= 1)
);

CREATE INDEX IF NOT EXISTS idx_stepstone_company_cycle_reviews_created
    ON stepstone_company_discovery_cycle_reviews (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_stepstone_company_cycle_reviews_scope
    ON stepstone_company_discovery_cycle_reviews (source_name, search_profile_name, search_term, created_at DESC);

CREATE TABLE IF NOT EXISTS stepstone_company_discovery_cycle_items (
    id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL
        REFERENCES stepstone_company_discovery_cycle_reviews(id)
        ON DELETE CASCADE,
    item_type TEXT NOT NULL,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    sample_titles JSONB NOT NULL DEFAULT '[]'::jsonb,
    reason TEXT NOT NULL,
    cooldown_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_stepstone_company_cycle_item_type CHECK (
        item_type IN ('observed_company', 'cooldown_proposal')
    ),
    CONSTRAINT chk_stepstone_company_cycle_item_counts CHECK (evidence_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_stepstone_company_cycle_items_review
    ON stepstone_company_discovery_cycle_items (review_id);

CREATE INDEX IF NOT EXISTS idx_stepstone_company_cycle_items_company
    ON stepstone_company_discovery_cycle_items (company_key, created_at DESC);
