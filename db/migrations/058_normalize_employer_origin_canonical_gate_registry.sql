-- Normalize employer-origin candidate gates to the canonical 16-gate registry.
--
-- A1e makes connector validation and final approval first-class gates.
-- This migration is robust against older action-style decisions such as
-- continue/build_connector_candidate/activate_controlled by mapping passed
-- gate action decisions to the constrained lifecycle decision 'passed' before
-- gate_order rows are touched.

UPDATE employer_origin_candidate_gate_reviews
SET decision = 'passed'
WHERE gate_status = 'passed'
  AND decision NOT IN (
      'passed',
      'ready_for_final_approval',
      'approve_connector_registration'
  );

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
UPDATE employer_origin_candidate_gate_reviews r
SET
    gate_order = g.gate_order,
    is_hard_gate = g.is_hard_gate
FROM official_gates g
WHERE r.gate_name = g.gate_name;

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
),
candidates AS (
    SELECT id AS candidate_id
    FROM employer_origin_source_candidates
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
    c.candidate_id,
    g.gate_name,
    g.gate_order,
    'not_started',
    'defer',
    g.is_hard_gate,
    NULL,
    '{}'::jsonb,
    NULL
FROM candidates c
CROSS JOIN official_gates g
ON CONFLICT (candidate_id, gate_name)
DO NOTHING;
