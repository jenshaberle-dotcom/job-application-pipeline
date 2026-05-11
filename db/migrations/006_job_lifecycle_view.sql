CREATE OR REPLACE VIEW job_lifecycle AS
SELECT
    source_name,
    external_job_id,
    MIN(observed_at) AS first_seen_at,
    MAX(observed_at) AS last_seen_at,
    COUNT(*) AS times_seen,
    EXTRACT(
        DAY FROM MAX(observed_at) - MIN(observed_at)
    )::integer AS days_observed
FROM job_observations
WHERE external_job_id IS NOT NULL
GROUP BY
    source_name,
    external_job_id;
