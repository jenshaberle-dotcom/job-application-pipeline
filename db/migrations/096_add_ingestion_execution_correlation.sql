ALTER TABLE ingestion_runs
ADD COLUMN IF NOT EXISTS execution_id UUID;

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_execution_id
ON ingestion_runs (execution_id)
WHERE execution_id IS NOT NULL;
