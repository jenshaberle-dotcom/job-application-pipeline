CREATE UNIQUE INDEX IF NOT EXISTS idx_job_observations_unique_run_source_job
ON job_observations (
    ingestion_run_id,
    source_name,
    external_job_id
)
WHERE external_job_id IS NOT NULL;
