ALTER TABLE ingestion_runs
ADD COLUMN IF NOT EXISTS error_type TEXT;

ALTER TABLE ingestion_runs
ADD COLUMN IF NOT EXISTS error_stage TEXT;

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_status_error_type
ON ingestion_runs (status, error_type);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_error_stage
ON ingestion_runs (error_stage)
WHERE status = 'failed';
