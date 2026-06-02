-- S7Q Allow Connector Validation Final-Approval Gate Decision
--
-- Purpose:
--   Allow the connector validation agent to persist a passed validation gate
--   that recommends the candidate for the next final-approval step.
--
-- Source:
--   Existing decision values were copied from db/migrations/024_extend_employer_origin_gate_decisions_for_s4.sql.
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
        'deferred'::text,
        'manual_review_required'::text,
        'skipped'::text,
        'not_applicable'::text,
        'ready_for_final_approval'::text
    ])) NOT VALID;
