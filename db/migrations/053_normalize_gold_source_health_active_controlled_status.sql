-- S7X normalize Gold source health status terminology.
--
-- Purpose:
--   The employer-origin candidate lifecycle uses active_controlled as the
--   canonical status value. The Gold health aggregate previously returned
--   controlled_active for the same state, which was understandable but
--   inconsistent across dashboard/read-model semantics.
--
-- Boundary:
-- - This migration only replaces the Gold read-model view.
-- - It does not update source candidates.
-- - It does not create search profiles.
-- - It does not run ingestion.
-- - It does not write raw_jobs, silver_jobs or snapshots.
-- - It does not change scheduler configuration.

CREATE OR REPLACE VIEW gold_source_health_summary AS
SELECT
    source_name_candidate AS source_name,
    source_family_candidate AS source_family,
    source_type_candidate AS source_type,
    source_role,
    count(*)::integer AS candidate_count,
    count(*) FILTER (WHERE candidate_status = 'active_controlled')::integer AS active_controlled_count,
    count(*) FILTER (WHERE current_stage = 'blocked_by_gate')::integer AS blocked_candidate_count,
    count(*) FILTER (WHERE current_stage = 'build_approval_required')::integer AS build_approval_required_count,
    count(*) FILTER (WHERE fn_pressure_level = ANY (ARRAY['high'::text, 'critical'::text]))::integer AS high_fn_pressure_count,
    CASE
        WHEN count(*) FILTER (WHERE fn_pressure_level = 'critical') > 0
            THEN 'attention_required'
        WHEN count(*) FILTER (
            WHERE current_stage = ANY (
                ARRAY[
                    'blocked_by_gate'::text,
                    'build_approval_required'::text,
                    'gate_reassessment_required'::text
                ]
            )
        ) > 0
            THEN 'review_required'
        WHEN count(*) FILTER (WHERE candidate_status = 'active_controlled') > 0
            THEN 'active_controlled'
        ELSE 'candidate_monitoring'
    END AS health_status,
    max(last_signal_at) AS last_signal_at,
    string_agg(DISTINCT blocking_gate, ', ' ORDER BY blocking_gate)
        FILTER (WHERE blocking_gate IS NOT NULL) AS blocking_gates
FROM gold_candidate_lifecycle_status
GROUP BY
    source_name_candidate,
    source_family_candidate,
    source_type_candidate,
    source_role;
