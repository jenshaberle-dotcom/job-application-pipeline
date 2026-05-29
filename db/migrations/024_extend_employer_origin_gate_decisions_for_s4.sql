-- S4 employer-origin gate vocabulary alignment.
--
-- Purpose:
--   S4A/S4B/S4C agents write validation, approval and registration-readiness
--   outcomes into employer_origin_candidate_gate_reviews. The original S2R
--   gate-state model allowed only the early generic decisions, which would make
--   later DB-backed agent steps fail at the database constraint boundary.
--
-- Boundary:
--   This migration only extends allowed gate status/decision vocabulary.
--   It does not activate sources, register connectors, write Bronze rows,
--   enable recurring ingestion or use export artifacts as inputs.

alter table employer_origin_candidate_gate_reviews
    drop constraint if exists employer_origin_candidate_gate_reviews_gate_status_check;

alter table employer_origin_candidate_gate_reviews
    add constraint employer_origin_candidate_gate_reviews_gate_status_check
        check (gate_status in (
            'not_started',
            'passed',
            'failed',
            'deferred',
            'manual_review_required',
            'skipped',
            'not_applicable'
        ));

alter table employer_origin_candidate_gate_reviews
    drop constraint if exists employer_origin_candidate_gate_reviews_decision_check;

alter table employer_origin_candidate_gate_reviews
    add constraint employer_origin_candidate_gate_reviews_decision_check
        check (decision in (
            'continue',
            'defer',
            'manual_review_required',
            'abort_documented',
            'build_connector_candidate',
            'activate_controlled',
            'disable_or_deprecate',
            'connector_validation_failed',
            'ready_for_final_approval',
            'approval_blocked',
            'approval_token_required',
            'approve_connector_registration',
            'monitor_existing_source',
            'stop_before_connector_generation',
            'connector_generation_allowed_before_final_approval'
        ));
