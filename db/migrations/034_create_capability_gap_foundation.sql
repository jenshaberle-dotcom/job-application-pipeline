-- S5H Capability Gap Foundation
--
-- Purpose:
--   Turn candidate intelligence and search-term value signals into explicit,
--   reviewable capability gaps. This is intentionally a market-signal-based
--   first foundation, not a full job-description fit engine.
--
-- Boundary:
--   - no search-profile mutation
--   - no source activation
--   - no Bronze writes
--   - no scheduler changes

CREATE TABLE IF NOT EXISTS capability_gap_scores (
    id BIGSERIAL PRIMARY KEY,
    profile_name TEXT NOT NULL,
    profile_version TEXT NOT NULL DEFAULT 'v1',
    skill_name TEXT NOT NULL,
    skill_category TEXT NOT NULL,
    capability_score INTEGER NOT NULL CHECK (capability_score BETWEEN 0 AND 100),
    career_direction_weight INTEGER NOT NULL CHECK (career_direction_weight BETWEEN 0 AND 100),
    growth_gap INTEGER NOT NULL CHECK (growth_gap BETWEEN 0 AND 100),
    supporting_term_count INTEGER NOT NULL DEFAULT 0,
    supporting_terms JSONB NOT NULL DEFAULT '[]'::jsonb,
    max_search_term_value NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (max_search_term_value BETWEEN 0 AND 100),
    avg_search_term_value NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (avg_search_term_value BETWEEN 0 AND 100),
    market_signal_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (market_signal_score BETWEEN 0 AND 100),
    priority_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (priority_score BETWEEN 0 AND 100),
    priority_band TEXT NOT NULL DEFAULT 'unknown',
    recommendation TEXT NOT NULL DEFAULT 'monitor',
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by TEXT NOT NULL DEFAULT 'agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (profile_name, profile_version, skill_name),
    CONSTRAINT chk_capability_gap_priority_band CHECK (
        priority_band = ANY (ARRAY['low'::text, 'medium'::text, 'high'::text, 'critical'::text, 'unknown'::text])
    ),
    CONSTRAINT chk_capability_gap_recommendation CHECK (
        recommendation = ANY (ARRAY['monitor'::text, 'practice_in_project'::text, 'prioritize_learning'::text, 'certification_candidate'::text])
    )
);

CREATE INDEX IF NOT EXISTS idx_capability_gap_scores_priority
    ON capability_gap_scores (priority_score DESC, priority_band, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_capability_gap_scores_profile
    ON capability_gap_scores (profile_name, profile_version, priority_score DESC);
