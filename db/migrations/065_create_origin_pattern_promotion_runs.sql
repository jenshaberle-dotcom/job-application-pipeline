-- A2D: Pattern promotion audit for adaptive origin observations.
--
-- Observation tables are learning input only. Promotion records which observed
-- patterns are allowed to influence later URL-finder / relevance-discovery
-- strategy. Promotion still must not pass gates, mutate candidate status,
-- activate sources, write Bronze/Silver jobs or bypass explicit approvals.

CREATE TABLE IF NOT EXISTS origin_pattern_promotion_runs (
    id BIGSERIAL PRIMARY KEY,
    run_label TEXT NOT NULL DEFAULT 'origin_pattern_promotion',
    promoted_count INTEGER NOT NULL DEFAULT 0,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    boundary JSONB NOT NULL DEFAULT '{
        "learning_input_only": true,
        "no_gate_decision": true,
        "no_candidate_status_mutation": true,
        "no_connector_artifact_generation": true,
        "no_connector_registration": true,
        "no_source_activation": true,
        "no_bronze_write": true,
        "no_silver_write": true,
        "no_scheduler_change": true,
        "no_csv_or_export_input": true,
        "pattern_usage_requires_promotion": true
    }'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'agent',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (promoted_count >= 0),
    CHECK (candidate_count >= 0),
    CHECK (rejected_count >= 0)
);

CREATE TABLE IF NOT EXISTS origin_pattern_promotion_decisions (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES origin_pattern_promotion_runs(id) ON DELETE CASCADE,
    observed_pattern_id BIGINT NOT NULL REFERENCES origin_observed_pattern_candidates(id) ON DELETE CASCADE,
    pattern_type TEXT NOT NULL,
    pattern_value TEXT NOT NULL,
    previous_status TEXT NOT NULL,
    promotion_status TEXT NOT NULL,
    confidence NUMERIC(10, 4) NOT NULL DEFAULT 0,
    signal_strength TEXT NOT NULL DEFAULT 'supporting',
    usable_by_url_finder BOOLEAN NOT NULL DEFAULT false,
    usable_by_relevance_probe BOOLEAN NOT NULL DEFAULT false,
    reason TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (promotion_status IN ('observed', 'candidate', 'promoted', 'rejected')),
    CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE INDEX IF NOT EXISTS idx_origin_pattern_promotion_decisions_run
    ON origin_pattern_promotion_decisions (run_id);

CREATE INDEX IF NOT EXISTS idx_origin_pattern_promotion_decisions_usage
    ON origin_pattern_promotion_decisions (pattern_type, promotion_status, usable_by_url_finder, usable_by_relevance_probe);

CREATE OR REPLACE VIEW gold_origin_promoted_observation_patterns AS
SELECT
    pattern_type,
    pattern_value,
    evidence_count,
    confidence,
    promotion_status,
    evidence,
    updated_at
FROM origin_observed_pattern_candidates
WHERE promotion_status = 'promoted';
