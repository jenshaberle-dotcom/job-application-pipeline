-- A2A: autonomous job-detail discovery and relevance signal learning.
--
-- Purpose:
--   Persist autonomously discovered employer-origin job-detail evidence and
--   learned classification signals. This replaces the rejected manual feedback
--   direction: humans may review outcomes, but the product path must not depend
--   on humans feeding job URLs into the pipeline.
--
-- Boundary:
-- - No connector registration or activation.
-- - No Bronze/Silver writes.
-- - No scheduler changes.
-- - Human-provided URLs are not modeled as product input here.

CREATE TABLE IF NOT EXISTS employer_origin_job_detail_evidence (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT NOT NULL REFERENCES employer_origin_source_candidates(id) ON DELETE CASCADE,
    company_key TEXT NOT NULL,
    source_url TEXT NOT NULL,
    final_url TEXT,
    evidence_host TEXT,
    path_pattern TEXT,
    status_code INTEGER,
    page_title TEXT,
    profile_hits JSONB NOT NULL DEFAULT '[]'::jsonb,
    location_hits JSONB NOT NULL DEFAULT '[]'::jsonb,
    remote_hits JSONB NOT NULL DEFAULT '[]'::jsonb,
    flexibility_hits JSONB NOT NULL DEFAULT '[]'::jsonb,
    relevance_decision TEXT NOT NULL,
    confidence NUMERIC(5, 4) NOT NULL DEFAULT 0.0000,
    reason TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    discovered_by TEXT NOT NULL,
    reviewed_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT employer_origin_job_detail_evidence_decision_check
        CHECK (relevance_decision IN ('relevant', 'insufficient_evidence', 'not_relevant')),
    CONSTRAINT employer_origin_job_detail_evidence_confidence_check
        CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT employer_origin_job_detail_evidence_unique_url
        UNIQUE (candidate_id, source_url)
);

CREATE INDEX IF NOT EXISTS idx_employer_origin_job_detail_evidence_candidate
    ON employer_origin_job_detail_evidence (candidate_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_employer_origin_job_detail_evidence_company
    ON employer_origin_job_detail_evidence (company_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_employer_origin_job_detail_evidence_host
    ON employer_origin_job_detail_evidence (evidence_host, path_pattern);

CREATE TABLE IF NOT EXISTS employer_origin_learned_relevance_signals (
    id BIGSERIAL PRIMARY KEY,
    signal_type TEXT NOT NULL,
    signal_value TEXT NOT NULL,
    signal_strength TEXT NOT NULL,
    confidence NUMERIC(5, 4) NOT NULL DEFAULT 0.0000,
    company_key TEXT NOT NULL DEFAULT '',
    source_family TEXT NOT NULL DEFAULT '',
    evidence_host TEXT NOT NULL DEFAULT '',
    path_pattern TEXT NOT NULL DEFAULT '',
    first_seen_candidate_id BIGINT REFERENCES employer_origin_source_candidates(id) ON DELETE SET NULL,
    last_seen_candidate_id BIGINT REFERENCES employer_origin_source_candidates(id) ON DELETE SET NULL,
    evidence_count INTEGER NOT NULL DEFAULT 1,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    learned_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT employer_origin_learned_relevance_signals_type_check
        CHECK (signal_type IN ('profile', 'target_location', 'remote_or_germany', 'flexibility', 'job_detail_path_pattern')),
    CONSTRAINT employer_origin_learned_relevance_signals_strength_check
        CHECK (signal_strength IN ('strong', 'medium', 'weak')),
    CONSTRAINT employer_origin_learned_relevance_signals_confidence_check
        CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_employer_origin_learned_relevance_signals_scope
    ON employer_origin_learned_relevance_signals (
        signal_type,
        signal_value,
        company_key,
        evidence_host,
        path_pattern
    );

CREATE INDEX IF NOT EXISTS idx_employer_origin_learned_relevance_signals_type
    ON employer_origin_learned_relevance_signals (signal_type, signal_strength, updated_at DESC);

COMMENT ON TABLE employer_origin_job_detail_evidence IS
    'Autonomously discovered bounded job-detail/search evidence for employer-origin relevance decisions.';

COMMENT ON TABLE employer_origin_learned_relevance_signals IS
    'DB-backed relevance/location/profile signals learned from accepted autonomous job-detail evidence.';
