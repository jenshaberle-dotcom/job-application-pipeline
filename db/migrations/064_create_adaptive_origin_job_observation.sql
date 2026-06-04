-- A2A Adaptive Origin Job Observation Loop
-- Purpose: learning input only. These tables must never directly pass gates,
-- activate sources, write Bronze/Silver jobs, or act as hidden pipeline inputs.

CREATE TABLE IF NOT EXISTS origin_job_observation_runs (
    id BIGSERIAL PRIMARY KEY,
    run_label TEXT NOT NULL DEFAULT 'adaptive_origin_job_observation',
    source_scope TEXT NOT NULL DEFAULT 'employer_origin_candidates',
    min_observations INTEGER NOT NULL DEFAULT 20,
    soft_cap INTEGER NOT NULL DEFAULT 40,
    hard_cap INTEGER NOT NULL DEFAULT 75,
    stop_reason TEXT,
    observed_page_count INTEGER NOT NULL DEFAULT 0,
    stored_full_observation_count INTEGER NOT NULL DEFAULT 0,
    summary_only_count INTEGER NOT NULL DEFAULT 0,
    discarded_count INTEGER NOT NULL DEFAULT 0,
    skipped_duplicate_url_count INTEGER NOT NULL DEFAULT 0,
    skipped_known_url_count INTEGER NOT NULL DEFAULT 0,
    skipped_saturated_host_count INTEGER NOT NULL DEFAULT 0,
    total_learning_value NUMERIC(10, 4) NOT NULL DEFAULT 0,
    max_learning_value NUMERIC(10, 4) NOT NULL DEFAULT 0,
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
        "adaptive_stop_or_extend": true
    }'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_by TEXT NOT NULL DEFAULT 'agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (min_observations > 0),
    CHECK (soft_cap >= min_observations),
    CHECK (hard_cap >= soft_cap),
    CHECK (observed_page_count >= 0),
    CHECK (stored_full_observation_count >= 0),
    CHECK (summary_only_count >= 0),
    CHECK (discarded_count >= 0),
    CHECK (skipped_duplicate_url_count >= 0),
    CHECK (skipped_known_url_count >= 0),
    CHECK (skipped_saturated_host_count >= 0)
);

CREATE TABLE IF NOT EXISTS origin_job_page_observations (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES origin_job_observation_runs(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    final_url TEXT,
    host TEXT,
    source_family_guess TEXT,
    status_code INTEGER,
    page_type_guess TEXT NOT NULL,
    title TEXT,
    ats_family_guess TEXT,
    has_json_ld_jobposting BOOLEAN NOT NULL DEFAULT false,
    visible_job_link_count INTEGER NOT NULL DEFAULT 0,
    detail_url_patterns JSONB NOT NULL DEFAULT '[]'::jsonb,
    location_signal_candidates JSONB NOT NULL DEFAULT '[]'::jsonb,
    remote_signal_candidates JSONB NOT NULL DEFAULT '[]'::jsonb,
    profile_signal_candidates JSONB NOT NULL DEFAULT '[]'::jsonb,
    structural_markers JSONB NOT NULL DEFAULT '[]'::jsonb,
    learning_value NUMERIC(10, 4) NOT NULL DEFAULT 0,
    novelty_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    storage_class TEXT NOT NULL,
    observation_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, source_url),
    CHECK (page_type_guess IN ('job_detail', 'search_listing', 'career_landing', 'ats_jobboard', 'error_or_blocked', 'unknown')),
    CHECK (storage_class IN ('full_observation', 'summary_only', 'discard_after_run')),
    CHECK (visible_job_link_count >= 0),
    CHECK (learning_value >= 0)
);

CREATE TABLE IF NOT EXISTS origin_observed_pattern_candidates (
    id BIGSERIAL PRIMARY KEY,
    pattern_type TEXT NOT NULL,
    pattern_value TEXT NOT NULL,
    evidence_count INTEGER NOT NULL DEFAULT 1,
    first_seen_run_id BIGINT REFERENCES origin_job_observation_runs(id) ON DELETE SET NULL,
    last_seen_run_id BIGINT REFERENCES origin_job_observation_runs(id) ON DELETE SET NULL,
    first_seen_observation_id BIGINT REFERENCES origin_job_page_observations(id) ON DELETE SET NULL,
    last_seen_observation_id BIGINT REFERENCES origin_job_page_observations(id) ON DELETE SET NULL,
    confidence NUMERIC(10, 4) NOT NULL DEFAULT 0.4,
    promotion_status TEXT NOT NULL DEFAULT 'observed',
    learning_notes TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pattern_type, pattern_value),
    CHECK (pattern_type IN ('url_path_pattern', 'ats_family', 'json_ld_jobposting', 'page_type', 'location_signal', 'remote_signal', 'profile_signal', 'structural_marker')),
    CHECK (promotion_status IN ('observed', 'candidate', 'promoted', 'rejected')),
    CHECK (evidence_count >= 1),
    CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE TABLE IF NOT EXISTS employer_origin_reprocess_benchmarks (
    id BIGSERIAL PRIMARY KEY,
    benchmark_label TEXT NOT NULL,
    phase TEXT NOT NULL,
    candidate_id BIGINT,
    company_key TEXT,
    company_name TEXT,
    candidate_status TEXT,
    current_stage TEXT,
    passed_gate_count INTEGER,
    blocked_gate_count INTEGER,
    total_gate_count INTEGER,
    blocking_gate TEXT,
    blocking_decision TEXT,
    blocker_reason TEXT,
    job_detail_evidence_count INTEGER NOT NULL DEFAULT 0,
    learned_signal_count INTEGER NOT NULL DEFAULT 0,
    action_run_count INTEGER NOT NULL DEFAULT 0,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (phase IN ('before', 'after'))
);

CREATE INDEX IF NOT EXISTS idx_origin_job_page_observations_run ON origin_job_page_observations(run_id);
CREATE INDEX IF NOT EXISTS idx_origin_job_page_observations_host ON origin_job_page_observations(host);
CREATE INDEX IF NOT EXISTS idx_origin_job_page_observations_storage ON origin_job_page_observations(storage_class);
CREATE INDEX IF NOT EXISTS idx_origin_observed_pattern_candidates_type ON origin_observed_pattern_candidates(pattern_type, promotion_status);
CREATE INDEX IF NOT EXISTS idx_employer_origin_reprocess_benchmarks_label_phase ON employer_origin_reprocess_benchmarks(benchmark_label, phase);
