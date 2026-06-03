-- S7X mark enercity as controlled-active after verified activation and first run.
--
-- Purpose:
--   Move the enercity employer-origin candidate from discovery to active_controlled
--   after the source target has passed the controlled activation chain:
--
--   S7V: search profile activation via 051_activate_enercity_discovery_source_target.sql
--   S7W: first controlled ingestion run succeeded
--   S7W: first controlled Silver transformation succeeded
--
-- Boundary:
-- - This migration updates only the employer-origin candidate lifecycle state.
-- - It does not create search profiles.
-- - It does not run ingestion.
-- - It does not write raw_jobs or silver_jobs.
-- - It does not change scheduler configuration.

UPDATE employer_origin_source_candidates
SET
    status = 'active_controlled',
    source_target_candidate = COALESCE(NULLIF(source_target_candidate, ''), 'discovery'),
    notes = CONCAT_WS(
        E'\n',
        notes,
        'S7X: marked active_controlled after controlled activation migration 051, first successful ingestion run 527, and Silver job 196.'
    ),
    updated_at = NOW()
WHERE company_key = 'enercity'
  AND source_name_candidate = 'enercity:discovery'
  AND status <> 'active_controlled'
  AND EXISTS (
      SELECT 1
      FROM search_profiles
      WHERE source_name = 'enercity:discovery'
        AND profile_name = 'enercity_discovery_hannover_precision'
        AND is_active = TRUE
  )
  AND EXISTS (
      SELECT 1
      FROM ingestion_runs
      WHERE source_name = 'enercity:discovery'
        AND status = 'success'
        AND inserted_count >= 1
  )
  AND EXISTS (
      SELECT 1
      FROM silver_jobs
      WHERE source_name = 'enercity:discovery'
  );
