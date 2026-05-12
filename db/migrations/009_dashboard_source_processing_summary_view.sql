DROP VIEW IF EXISTS dashboard_source_processing_summary;

CREATE VIEW dashboard_source_processing_summary AS
SELECT
    source_name,

    COUNT(*) AS ingestion_run_count,

    COUNT(*) FILTER (
        WHERE status = 'success'
    ) AS successful_run_count,

    COUNT(*) FILTER (
        WHERE status = 'failed'
    ) AS failed_run_count,

    MAX(started_at) AS latest_ingestion_at,

    MAX(finished_at) FILTER (
        WHERE status = 'success'
    ) AS latest_successful_ingestion_at,

    SUM(total_loaded) AS total_loaded_jobs,
    SUM(inserted_count) AS total_inserted_jobs,
    SUM(duplicate_count) AS total_duplicate_jobs,

    SUM(new_raw_jobs) AS total_new_raw_jobs,
    SUM(new_relevant_jobs) AS total_new_relevant_jobs,
    SUM(new_skipped_jobs) AS total_new_skipped_jobs,
    SUM(new_unprocessed_jobs) AS total_new_unprocessed_jobs,

    SUM(new_unprocessed_jobs) > 0 AS has_unprocessed_jobs,

    ROUND(
        SUM(duplicate_count)::numeric
        / NULLIF(SUM(total_loaded), 0),
        4
    ) AS duplicate_rate,

    ROUND(
        SUM(new_relevant_jobs)::numeric
        / NULLIF(SUM(new_raw_jobs), 0),
        4
    ) AS new_relevance_rate

FROM dashboard_new_relevant_jobs
GROUP BY source_name;
