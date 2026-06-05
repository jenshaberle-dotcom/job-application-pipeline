-- Extend Search Intelligence action-run audit types for A1f.
--
-- A1f introduces a generic next-safe-action orchestrator so the Control Center
-- can choose the appropriate bounded action for a candidate instead of forcing
-- users to manually pick a specific repair/validation step. The action-run audit
-- table must allow this new operational action type before the GUI can persist
-- the run.

ALTER TABLE search_intelligence_action_runs
DROP CONSTRAINT IF EXISTS chk_search_intelligence_action_runs_action_type;

ALTER TABLE search_intelligence_action_runs
ADD CONSTRAINT chk_search_intelligence_action_runs_action_type
CHECK (
    action_type IN (
        'rerun_evidence_repair',
        'continue_candidate_review',
        'run_connector_validation',
        'run_next_safe_action',
        'approve_connector_build',
        'approve_connector_registration'
    )
);
