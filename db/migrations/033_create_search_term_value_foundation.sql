-- S5G-C Vocabulary Quality & Search-Term Value Foundation
--
-- Purpose:
--   Score observed company vocabulary and combine it with the candidate profile
--   so search-intelligence can distinguish raw vocabulary from terms that are
--   valuable for Jens' Data Engineer direction.
--
-- Boundary:
--   - no search-profile mutation
--   - no source activation
--   - no Bronze writes
--   - no scheduler changes

CREATE TABLE IF NOT EXISTS vocabulary_signal_scores (
    id BIGSERIAL PRIMARY KEY,
    observed_term TEXT NOT NULL,
    company_count INTEGER NOT NULL DEFAULT 0,
    observation_count INTEGER NOT NULL DEFAULT 0,
    noise_penalty INTEGER NOT NULL DEFAULT 0 CHECK (noise_penalty BETWEEN 0 AND 100),
    signal_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (signal_score BETWEEN 0 AND 100),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by TEXT NOT NULL DEFAULT 'agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (observed_term)
);

CREATE INDEX IF NOT EXISTS idx_vocabulary_signal_scores_score
    ON vocabulary_signal_scores (signal_score DESC, observation_count DESC, company_count DESC);

CREATE TABLE IF NOT EXISTS search_term_value_scores (
    id BIGSERIAL PRIMARY KEY,
    observed_term TEXT NOT NULL,
    profile_name TEXT NOT NULL,
    profile_version TEXT NOT NULL DEFAULT 'v1',
    matched_skill_name TEXT,
    matched_skill_category TEXT,
    vocabulary_signal_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (vocabulary_signal_score BETWEEN 0 AND 100),
    career_direction_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (career_direction_score BETWEEN 0 AND 100),
    capability_alignment_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (capability_alignment_score BETWEEN 0 AND 100),
    growth_gap_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (growth_gap_score BETWEEN 0 AND 100),
    overall_value_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (overall_value_score BETWEEN 0 AND 100),
    value_band TEXT NOT NULL DEFAULT 'unknown',
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by TEXT NOT NULL DEFAULT 'agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (observed_term, profile_name, profile_version),
    CONSTRAINT chk_search_term_value_band CHECK (
        value_band = ANY (ARRAY['low'::text, 'medium'::text, 'high'::text, 'strategic'::text, 'unknown'::text])
    )
);

CREATE INDEX IF NOT EXISTS idx_search_term_value_scores_overall
    ON search_term_value_scores (overall_value_score DESC, value_band, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_term_value_scores_profile
    ON search_term_value_scores (profile_name, profile_version, overall_value_score DESC);
