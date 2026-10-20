CREATE TABLE IF NOT EXISTS bronze_native_census_runs (
    run_id text PRIMARY KEY,
    source_sha text NOT NULL,
    state text NOT NULL,
    summary jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS bronze_native_census_sources (
    run_id text NOT NULL REFERENCES bronze_native_census_runs(run_id),
    source_id text NOT NULL,
    state text NOT NULL,
    payload jsonb NOT NULL,
    payload_digest text NOT NULL,
    PRIMARY KEY (run_id, source_id)
);
CREATE TABLE IF NOT EXISTS bronze_native_census_candidates (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id text NOT NULL REFERENCES bronze_native_census_runs(run_id),
    company_key text NOT NULL,
    observation jsonb NOT NULL,
    batch_index integer NOT NULL,
    UNIQUE (run_id, company_key)
);
CREATE TABLE IF NOT EXISTS bronze_native_census_http (
    run_id text NOT NULL REFERENCES bronze_native_census_runs(run_id),
    source_id text NOT NULL,
    response_id text NOT NULL,
    url text NOT NULL,
    sha256 text NOT NULL,
    body bytea NOT NULL,
    PRIMARY KEY (run_id, source_id, response_id)
);
CREATE TABLE IF NOT EXISTS native_census_factory_results (
    candidate_id bigint PRIMARY KEY REFERENCES bronze_native_census_candidates(id),
    state text NOT NULL,
    result jsonb NOT NULL,
    completed_at timestamptz NOT NULL DEFAULT now()
);
