ALTER TABLE ingestion_runs
ADD COLUMN IF NOT EXISTS execution_id UUID;

-- Historical rows deliberately remain NULL. New canonical src.ingest_jobs
-- invocations set PGAPPNAME=job-pipeline-ingest:<uuid>; libpq exposes that as
-- application_name on every connection opened by the invocation, so all profile
-- and search-term ingestion_runs created inside one invocation receive the same
-- correlation without a timestamp heuristic or duplicate lineage column.
ALTER TABLE ingestion_runs
ALTER COLUMN execution_id SET DEFAULT (
    CASE
        WHEN current_setting('application_name', TRUE) LIKE 'job-pipeline-ingest:%'
        THEN NULLIF(
            split_part(current_setting('application_name', TRUE), ':', 2),
            ''
        )::UUID
        ELSE NULL
    END
);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_execution_id
ON ingestion_runs (execution_id)
WHERE execution_id IS NOT NULL;
