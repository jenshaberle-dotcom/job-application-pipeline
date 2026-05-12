DROP VIEW IF EXISTS dashboard_new_relevant_jobs;

CREATE VIEW dashboard_new_relevant_jobs AS
SELECT
    ir.id AS ingestion_run_id,
    ir.source_name,
    sp.profile_name,
    ir.started_at,
    ir.finished_at,
    ir.status,
    ir.total_loaded,
    ir.inserted_count,
    ir.duplicate_count,

    COUNT(r.id) AS new_raw_jobs,

    COUNT(r.id) FILTER (
        WHERE spd.decision = 'included'
           OR sj.id IS NOT NULL
    ) AS new_relevant_jobs,

    COUNT(r.id) FILTER (
        WHERE spd.decision = 'skipped'
          AND sj.id IS NULL
    ) AS new_skipped_jobs,

    COUNT(r.id) FILTER (
        WHERE r.id IS NOT NULL
          AND spd.id IS NULL
          AND sj.id IS NULL
    ) AS new_unprocessed_jobs

FROM ingestion_runs ir
LEFT JOIN search_profiles sp
    ON sp.id = ir.search_profile_id
LEFT JOIN raw_jobs r
    ON r.ingestion_run_id = ir.id
LEFT JOIN silver_processing_decisions spd
    ON spd.raw_job_id = r.id
LEFT JOIN silver_jobs sj
    ON sj.raw_job_id = r.id
GROUP BY
    ir.id,
    ir.source_name,
    sp.profile_name,
    ir.started_at,
    ir.finished_at,
    ir.status,
    ir.total_loaded,
    ir.inserted_count,
    ir.duplicate_count;
