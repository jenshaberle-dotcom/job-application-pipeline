-- S5G-B Candidate Intelligence Foundation
--
-- Purpose:
--   Store a first explicit candidate profile for search-intelligence scoring.
--   This is intentionally separate from search profiles and source activation.
--
-- Boundary:
--   - no search-profile mutation
--   - no source activation
--   - no Bronze writes
--   - no scheduler changes

CREATE TABLE IF NOT EXISTS candidate_profiles (
    id BIGSERIAL PRIMARY KEY,
    profile_name TEXT NOT NULL,
    target_role TEXT NOT NULL,
    profile_version TEXT NOT NULL DEFAULT 'v1',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (profile_name, profile_version)
);

CREATE INDEX IF NOT EXISTS idx_candidate_profiles_target_role
    ON candidate_profiles (target_role);

CREATE TABLE IF NOT EXISTS candidate_skills (
    id BIGSERIAL PRIMARY KEY,
    candidate_profile_id BIGINT NOT NULL REFERENCES candidate_profiles(id) ON DELETE CASCADE,
    skill_name TEXT NOT NULL,
    skill_category TEXT NOT NULL,
    capability_score INTEGER NOT NULL CHECK (capability_score BETWEEN 0 AND 100),
    career_direction_weight INTEGER NOT NULL CHECK (career_direction_weight BETWEEN 0 AND 100),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (candidate_profile_id, skill_name)
);

CREATE INDEX IF NOT EXISTS idx_candidate_skills_profile_category
    ON candidate_skills (candidate_profile_id, skill_category);

CREATE INDEX IF NOT EXISTS idx_candidate_skills_direction_gap
    ON candidate_skills (career_direction_weight DESC, capability_score ASC);
