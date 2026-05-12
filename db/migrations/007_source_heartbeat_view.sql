DROP VIEW IF EXISTS source_heartbeat;

CREATE VIEW source_heartbeat AS
WITH latest_runs AS (
    SELECT
        ingestion_runs.*,
        ROW_NUMBER() OVER (
            PARTITION BY source_name
            ORDER BY started_at DESC, id DESC
        ) AS run_rank
    FROM ingestion_runs
)
SELECT
    source_name,
    id AS last_ingestion_run_id,
    started_at AS last_started_at,
    finished_at AS last_finished_at,
    status AS last_status,
    total_loaded AS last_total_loaded,
    inserted_count AS last_inserted_count,
    duplicate_count AS last_duplicate_count,
    error_message AS last_error_message,
    CASE
        WHEN status = 'success' THEN 'healthy'
        WHEN status = 'running' THEN 'running'
        WHEN status = 'failed' THEN 'failed'
        ELSE 'unknown'
    END AS heartbeat_status
FROM latest_runs
WHERE run_rank = 1;
