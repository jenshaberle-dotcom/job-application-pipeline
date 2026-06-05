-- A2E: Observation seed-pool expansion with source-type boundaries.
--
-- Seed-pool records are learning/discovery input only. They may prioritize URL
-- discovery and observation, but must not pass candidate gates, mutate candidate
-- status, activate sources, register connectors or write Bronze/Silver data.

CREATE TABLE IF NOT EXISTS origin_observation_seed_pool_snapshots (
    id BIGSERIAL PRIMARY KEY,
    run_label TEXT NOT NULL DEFAULT 'origin_observation_seed_pool',
    seed_key TEXT NOT NULL,
    seed_type TEXT NOT NULL,
    seed_source_table TEXT NOT NULL,
    observation_role TEXT NOT NULL,
    company_key TEXT,
    company_name TEXT,
    source_name TEXT,
    source_family TEXT,
    seed_url TEXT,
    url_allowed_for_observation BOOLEAN NOT NULL DEFAULT false,
    priority_score NUMERIC(10, 4) NOT NULL DEFAULT 0,
    prior_reason TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (seed_type IN (
        'origin_url_seed',
        'company_name_only_seed',
        'job_text_signal_seed',
        'ats_structure_seed',
        'aggregator_company_seed',
        'unknown_seed'
    )),
    CHECK (observation_role IN (
        'origin_url_observation',
        'url_discovery_input',
        'text_signal_learning',
        'ats_structure_learning',
        'company_discovery_only',
        'diagnostics_only'
    )),
    CHECK (priority_score >= 0 AND priority_score <= 1)
);

CREATE INDEX IF NOT EXISTS idx_origin_observation_seed_pool_type
    ON origin_observation_seed_pool_snapshots (seed_type, observation_role, priority_score DESC);

CREATE INDEX IF NOT EXISTS idx_origin_observation_seed_pool_company
    ON origin_observation_seed_pool_snapshots (company_key, seed_type);

CREATE INDEX IF NOT EXISTS idx_origin_observation_seed_pool_url
    ON origin_observation_seed_pool_snapshots (seed_url)
    WHERE seed_url IS NOT NULL;

ALTER TABLE origin_job_observation_runs
ADD COLUMN IF NOT EXISTS seed_source_type_counts JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE origin_job_observation_runs
ADD COLUMN IF NOT EXISTS skipped_by_policy_counts JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE origin_job_observation_runs
ADD COLUMN IF NOT EXISTS observed_by_source_type_counts JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE origin_job_observation_runs
ADD COLUMN IF NOT EXISTS learning_value_by_source_type JSONB NOT NULL DEFAULT '{}'::jsonb;
