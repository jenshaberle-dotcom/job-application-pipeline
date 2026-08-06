-- 089_add_candidate_origin_url_replacement_decision.sql
--
-- Extend the existing CAND-001 audit history for the separate, approval-gated
-- replacement of a populated candidate_url after fresh live S7N confirmation.
--
-- This migration grants no replacement authority by itself. Runtime apply still
-- requires exact target binding, expected-old-URL compare-and-set, live bounded
-- repair evidence and an explicit approval token.

ALTER TABLE candidate_origin_url_persistence_reviews
    DROP CONSTRAINT IF EXISTS chk_candidate_origin_url_persistence_decision;

ALTER TABLE candidate_origin_url_persistence_reviews
    ADD CONSTRAINT chk_candidate_origin_url_persistence_decision CHECK (
        decision = ANY (ARRAY[
            'persist_validated_candidate_url'::text,
            'replace_validated_candidate_url'::text,
            'no_action_already_persisted'::text,
            'manual_review_required'::text,
            'manual_review_required_url_conflict'::text,
            'manual_review_required_duplicate_url'::text,
            'no_selected_url'::text,
            'skip_protected_active_controlled'::text
        ])
    );

CREATE OR REPLACE VIEW gold_candidate_origin_url_persistence_review_history AS
SELECT
    r.id AS persistence_review_id,
    r.candidate_id,
    r.company_key,
    r.company_name,
    r.previous_candidate_url,
    r.selected_candidate_url,
    r.selected_url_source,
    r.decision,
    r.review_status,
    r.reason,
    r.reviewed_by,
    r.applied_at,
    r.created_at,
    c.status AS candidate_status,
    c.candidate_url AS current_candidate_url
FROM candidate_origin_url_persistence_reviews r
JOIN employer_origin_source_candidates c ON c.id = r.candidate_id;

COMMENT ON CONSTRAINT chk_candidate_origin_url_persistence_decision
    ON candidate_origin_url_persistence_reviews IS
    'Allows initial persistence and separately approval-gated validated URL replacement decisions.';
