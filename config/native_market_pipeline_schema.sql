CREATE TABLE IF NOT EXISTS rcc_market_pipeline_runs (
 execution_key text PRIMARY KEY,
 occurrence text NOT NULL UNIQUE,
 source_sha text NOT NULL,
 state text NOT NULL,
 population jsonb NOT NULL DEFAULT '[]'::jsonb,
 result jsonb NOT NULL DEFAULT '{}'::jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),
 finished_at timestamptz
);
CREATE TABLE IF NOT EXISTS rcc_market_pipeline_candidates (
 company_key text PRIMARY KEY,
 first_seen timestamptz NOT NULL DEFAULT now(),
 last_seen timestamptz NOT NULL DEFAULT now(),
 last_attempt timestamptz,
 attempted_source_sha text,
 attempted_identity_sha256 text,
 last_result jsonb NOT NULL DEFAULT '{}'::jsonb
);
