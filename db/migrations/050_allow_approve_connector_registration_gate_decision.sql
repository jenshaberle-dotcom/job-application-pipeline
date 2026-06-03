-- S7R Allow Connector Registration Approval Gate Decision
--
-- Purpose:
--   Allow the final approval gate to persist an explicit connector-registration
--   approval decision after connector validation has passed.
--
-- Boundary:
--   Schema contract update only. This migration does not register connectors,
--   activate sources, write Bronze records or change scheduler configuration.

ALTER TABLE IF EXISTS employer_origin_candidate_gate_reviews
    DROP CONSTRAINT IF EXISTS employer_origin_candidate_gate_reviews_decision_check;

ALTER TABLE IF EXISTS employer_origin_candidate_gate_reviews
    ADD CONSTRAINT employer_origin_candidate_gate_reviews_decision_check
    CHECK (decision = ANY (ARRAY[
        'not_started'::text,
        'passed'::text,
        'failed'::text,
        'defer'::text,
        'deferred'::text,
        'manual_review_required'::text,
        'skipped'::text,
        'not_applicable'::text,
        'ready_for_final_approval'::text,
        'approve_connector_registration'::text
    ])) NOT VALID;
