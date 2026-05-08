CREATE TABLE IF NOT EXISTS silver_jobs (
    id BIGSERIAL PRIMARY KEY,

    raw_job_id BIGINT NOT NULL UNIQUE REFERENCES raw_jobs(id),

    source_name TEXT NOT NULL,
    external_job_id TEXT,
    source_url TEXT,

    title TEXT,
    company_name TEXT,

    city TEXT,
    postal_code TEXT,
    country TEXT,

    publication_date DATE,

    normalized_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_silver_jobs_source_name
ON silver_jobs (source_name);

CREATE INDEX IF NOT EXISTS idx_silver_jobs_external_job_id
ON silver_jobs (external_job_id);

CREATE INDEX IF NOT EXISTS idx_silver_jobs_company_name
ON silver_jobs (company_name);

CREATE INDEX IF NOT EXISTS idx_silver_jobs_city
ON silver_jobs (city);

CREATE INDEX IF NOT EXISTS idx_silver_jobs_publication_date
ON silver_jobs (publication_date);
