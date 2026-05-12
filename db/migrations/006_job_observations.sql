CREATE TABLE IF NOT EXISTS job_observations (
    id BIGSERIAL PRIMARY KEY,

    source_name TEXT NOT NULL,
    external_job_id TEXT,
    source_url TEXT,

    ingestion_run_id BIGINT
        REFERENCES ingestion_runs(id),

    raw_job_id BIGINT
        REFERENCES raw_jobs(id),

    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_seen BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_job_observations_source_external_id
ON job_observations(source_name, external_job_id);

CREATE INDEX IF NOT EXISTS idx_job_observations_observed_at
ON job_observations(observed_at);

CREATE INDEX IF NOT EXISTS idx_job_observations_ingestion_run_id
ON job_observations(ingestion_run_id);

CREATE INDEX IF NOT EXISTS idx_job_observations_raw_job_id
ON job_observations(raw_job_id);
