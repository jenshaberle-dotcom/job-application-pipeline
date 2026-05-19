ALTER TABLE silver_jobs
ADD COLUMN IF NOT EXISTS normalized_title TEXT;

ALTER TABLE silver_jobs
ADD COLUMN IF NOT EXISTS normalized_company_name TEXT;

ALTER TABLE silver_jobs
ADD COLUMN IF NOT EXISTS normalized_location TEXT;

ALTER TABLE silver_jobs
ADD COLUMN IF NOT EXISTS canonical_status TEXT;

ALTER TABLE silver_jobs
ADD COLUMN IF NOT EXISTS canonical_source_type TEXT;

ALTER TABLE silver_jobs
ADD COLUMN IF NOT EXISTS canonical_key_candidate TEXT;

CREATE INDEX IF NOT EXISTS idx_silver_jobs_normalized_company_name
ON silver_jobs (normalized_company_name);

CREATE INDEX IF NOT EXISTS idx_silver_jobs_normalized_title
ON silver_jobs (normalized_title);

CREATE INDEX IF NOT EXISTS idx_silver_jobs_canonical_status
ON silver_jobs (canonical_status);

CREATE INDEX IF NOT EXISTS idx_silver_jobs_canonical_key_candidate
ON silver_jobs (canonical_key_candidate);
