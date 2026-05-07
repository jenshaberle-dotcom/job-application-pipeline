CREATE TABLE IF NOT EXISTS search_profiles (
    id BIGSERIAL PRIMARY KEY,
    profile_name TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    search_location TEXT NOT NULL,
    search_radius_km INTEGER NOT NULL,
    offer_type INTEGER NOT NULL DEFAULT 1,
    page_size INTEGER NOT NULL DEFAULT 10,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    search_profile_id BIGINT REFERENCES search_profiles(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    requested_url TEXT,
    total_loaded INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

ALTER TABLE raw_jobs
ADD COLUMN IF NOT EXISTS ingestion_run_id BIGINT REFERENCES ingestion_runs(id);

ALTER TABLE raw_jobs
ADD COLUMN IF NOT EXISTS search_profile_id BIGINT REFERENCES search_profiles(id);

CREATE INDEX IF NOT EXISTS idx_raw_jobs_ingestion_run_id
ON raw_jobs (ingestion_run_id);

CREATE INDEX IF NOT EXISTS idx_raw_jobs_search_profile_id
ON raw_jobs (search_profile_id);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_search_profile_id
ON ingestion_runs (search_profile_id);

INSERT INTO search_profiles (
    profile_name,
    source_name,
    search_term,
    search_location,
    search_radius_km,
    offer_type,
    page_size
)
VALUES (
    'ba_data_engineer_30629_50km',
    'bundesagentur_fuer_arbeit',
    'Data Engineer',
    '30629',
    50,
    1,
    10
)
ON CONFLICT (profile_name) DO NOTHING;
