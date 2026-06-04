-- Extend Search Intelligence action-run audit types for A1c.
--
-- 055 introduced the search_intelligence_action_runs table.
-- A1c adds continue_candidate_review so candidates can be re-evaluated
-- from the Review Queue after the multi-origin evidence logic changed.

ALTER TABLE search_intelligence_action_runs
DROP CONSTRAINT IF EXISTS chk_search_intelligence_action_runs_action_type;

ALTER TABLE search_intelligence_action_runs
ADD CONSTRAINT chk_search_intelligence_action_runs_action_type
CHECK (
    action_type IN (
        'rerun_evidence_repair',
        'continue_candidate_review',
        'approve_connector_build',
        'approve_connector_registration'
    )
);
