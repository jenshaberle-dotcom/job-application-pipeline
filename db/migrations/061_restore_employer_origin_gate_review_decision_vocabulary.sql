-- Restore employer-origin gate-review decision vocabulary after canonical gate normalization.
--
-- A1e normalized passed gate action decisions to the canonical decision 'passed',
-- while preserving specific workflow actions in evidence or in dedicated approval
-- decisions such as ready_for_final_approval and approve_connector_registration.
-- Later gate-agent runs must therefore write 'passed' for passed gates, but the
-- constraint still needs to allow documented stop/review decisions used by the
-- existing agent family.
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
        'abort_documented'::text,
        'ready_for_final_approval'::text,
        'approve_connector_registration'::text,
        'connector_validation_failed'::text,
        'approval_blocked'::text,
        'approval_token_required'::text,
        'monitor_existing_source'::text,
        'stop_before_connector_generation'::text,
        'connector_generation_allowed_before_final_approval'::text,
        'disable_or_deprecate'::text
    ])) NOT VALID;
