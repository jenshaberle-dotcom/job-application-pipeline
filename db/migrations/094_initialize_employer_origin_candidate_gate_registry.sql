-- Ensure every employer-origin candidate has the complete canonical gate registry.
--
-- Issue #514 exposed a lifecycle invariant gap: candidates created after migration
-- 058 could exist without the canonical gate-review rows required by later gates.
-- This migration closes that gap at the database boundary so every future
-- candidate insert initializes the same 16-gate registry in the same transaction.
-- Existing gate state, decisions, evidence and reviewer metadata are preserved:
-- the backfill and trigger only insert missing (candidate_id, gate_name) rows.
--
-- Boundary:
--   Registry initialization only. This migration does not execute gates, register
--   connectors, activate sources, write Bronze/Silver records or change schedules.

CREATE OR REPLACE FUNCTION initialize_employer_origin_candidate_gate_registry()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO employer_origin_candidate_gate_reviews (
        candidate_id,
        gate_name,
        gate_order,
        gate_status,
        decision,
        is_hard_gate,
        stop_reason,
        evidence,
        reviewed_by
    )
    VALUES
        (NEW.id, 'company_candidate', 1, 'not_started', 'defer', false, NULL, '{}'::jsonb, NULL),
        (NEW.id, 'source_discovery', 2, 'not_started', 'defer', true, NULL, '{}'::jsonb, NULL),
        (NEW.id, 'risk_gate', 3, 'not_started', 'defer', true, NULL, '{}'::jsonb, NULL),
        (NEW.id, 'technical_reachability_gate', 4, 'not_started', 'defer', true, NULL, '{}'::jsonb, NULL),
        (NEW.id, 'scope_gate', 5, 'not_started', 'defer', true, NULL, '{}'::jsonb, NULL),
        (NEW.id, 'defensive_preview_gate', 6, 'not_started', 'defer', true, NULL, '{}'::jsonb, NULL),
        (NEW.id, 'relevance_gate', 7, 'not_started', 'defer', true, NULL, '{}'::jsonb, NULL),
        (NEW.id, 'detail_evidence_gate', 8, 'not_started', 'defer', true, NULL, '{}'::jsonb, NULL),
        (NEW.id, 'incremental_uniqueness_gate', 9, 'not_started', 'defer', true, NULL, '{}'::jsonb, NULL),
        (NEW.id, 'connector_candidate_gate', 10, 'not_started', 'defer', true, NULL, '{}'::jsonb, NULL),
        (NEW.id, 'connector_validation_gate', 11, 'not_started', 'defer', true, NULL, '{}'::jsonb, NULL),
        (NEW.id, 'final_approval_gate', 12, 'not_started', 'defer', true, NULL, '{}'::jsonb, NULL),
        (NEW.id, 'controlled_activation_gate', 13, 'not_started', 'defer', true, NULL, '{}'::jsonb, NULL),
        (NEW.id, 'bronze_validation', 14, 'not_started', 'defer', true, NULL, '{}'::jsonb, NULL),
        (NEW.id, 'silver_validation', 15, 'not_started', 'defer', true, NULL, '{}'::jsonb, NULL),
        (NEW.id, 'source_lifecycle_tracking', 16, 'not_started', 'defer', false, NULL, '{}'::jsonb, NULL)
    ON CONFLICT (candidate_id, gate_name)
    DO NOTHING;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS employer_origin_candidate_gate_registry_after_insert
    ON employer_origin_source_candidates;

CREATE TRIGGER employer_origin_candidate_gate_registry_after_insert
AFTER INSERT ON employer_origin_source_candidates
FOR EACH ROW
EXECUTE FUNCTION initialize_employer_origin_candidate_gate_registry();

WITH official_gates(gate_order, gate_name, is_hard_gate) AS (
    VALUES
        (1,  'company_candidate', false),
        (2,  'source_discovery', true),
        (3,  'risk_gate', true),
        (4,  'technical_reachability_gate', true),
        (5,  'scope_gate', true),
        (6,  'defensive_preview_gate', true),
        (7,  'relevance_gate', true),
        (8,  'detail_evidence_gate', true),
        (9,  'incremental_uniqueness_gate', true),
        (10, 'connector_candidate_gate', true),
        (11, 'connector_validation_gate', true),
        (12, 'final_approval_gate', true),
        (13, 'controlled_activation_gate', true),
        (14, 'bronze_validation', true),
        (15, 'silver_validation', true),
        (16, 'source_lifecycle_tracking', false)
)
INSERT INTO employer_origin_candidate_gate_reviews (
    candidate_id,
    gate_name,
    gate_order,
    gate_status,
    decision,
    is_hard_gate,
    stop_reason,
    evidence,
    reviewed_by
)
SELECT
    candidate.id,
    gate.gate_name,
    gate.gate_order,
    'not_started',
    'defer',
    gate.is_hard_gate,
    NULL,
    '{}'::jsonb,
    NULL
FROM employer_origin_source_candidates AS candidate
CROSS JOIN official_gates AS gate
ON CONFLICT (candidate_id, gate_name)
DO NOTHING;
