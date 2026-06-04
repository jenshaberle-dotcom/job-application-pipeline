-- Extend Search Intelligence action-run audit types for connector validation.
--
-- A1d adds a Review Queue action for connector candidates that already passed
-- evidence and connector-candidate gates. This is intentionally separate from
-- continue_candidate_review because validation is the next explicit workflow.

ALTER TABLE search_intelligence_action_runs
DROP CONSTRAINT IF EXISTS chk_search_intelligence_action_runs_action_type;

ALTER TABLE search_intelligence_action_runs
ADD CONSTRAINT chk_search_intelligence_action_runs_action_type
CHECK (
    action_type IN (
        'rerun_evidence_repair',
        'continue_candidate_review',
        'run_connector_validation',
        'approve_connector_build',
        'approve_connector_registration'
    )
);
