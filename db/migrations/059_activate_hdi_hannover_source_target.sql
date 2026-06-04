-- A1G controlled HDI source-target activation.
--
-- This migration activates exactly one bounded employer-origin source target:
--   source_name = 'hdi:hannover'
--
-- Preconditions documented in prior gates:
-- - connector_candidate_gate passed
-- - connector_validation_gate passed with ready_for_final_approval
-- - final_approval_gate passed with approve_connector_registration
-- - connector is code-backed in src.connectors.employer_origin_registry
--
-- Boundary:
-- - This migration creates one active search profile and bounded active search terms.
-- - It does not run ingestion.
-- - It does not write raw_jobs or silver_jobs.
-- - It does not create scheduler changes.
-- - It does not use CSV/Excel/export artifacts as inputs.

INSERT INTO search_profiles (
    profile_name,
    source_name,
    search_location,
    search_radius_km,
    offer_type,
    page_size,
    is_active
)
SELECT
    'hdi_hannover_precision',
    'hdi:hannover',
    'Hannover',
    50,
    1,
    3,
    true
WHERE NOT EXISTS (
    SELECT 1
    FROM search_profiles
    WHERE profile_name = 'hdi_hannover_precision'
);

WITH active_profile AS (
    SELECT id
    FROM search_profiles
    WHERE profile_name = 'hdi_hannover_precision'
), desired_terms(search_term) AS (
    VALUES
        ('Data'),
        ('Daten'),
        ('Analytics'),
        ('Business Intelligence'),
        ('BI'),
        ('SQL'),
        ('Python'),
        ('KI'),
        ('AI'),
        ('Software'),
        ('Entwickler'),
        ('JavaScript'),
        ('UI'),
        ('Product Owner'),
        ('Business Analyst'),
        ('Cloud'),
        ('Azure'),
        ('DevOps')
)
INSERT INTO search_terms (search_profile_id, search_term, is_active)
SELECT active_profile.id, desired_terms.search_term, true
FROM active_profile
CROSS JOIN desired_terms
WHERE NOT EXISTS (
    SELECT 1
    FROM search_terms existing
    WHERE existing.search_profile_id = active_profile.id
      AND lower(existing.search_term) = lower(desired_terms.search_term)
);

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
    c.id,
    'controlled_activation_gate',
    13,
    'passed',
    'passed',
    true,
    NULL,
    jsonb_build_object(
        'finding', 'HDI source target activated as hdi:hannover via controlled activation migration.',
        'activation_decision', 'activate_controlled',
        'profile_name', 'hdi_hannover_precision',
        'source_name', 'hdi:hannover',
        'boundary', jsonb_build_object(
            'source_activation_allowed', true,
            'bronze_persistence_allowed', false,
            'recurring_ingestion_allowed', false,
            'scheduler_change_allowed', false,
            'csv_or_export_inputs_used', false
        )
    ),
    'jens'
FROM employer_origin_source_candidates c
WHERE c.company_key = 'hdi'
  AND c.source_name_candidate = 'hdi:hannover'
ON CONFLICT (candidate_id, gate_name)
DO UPDATE SET
    gate_order = EXCLUDED.gate_order,
    gate_status = EXCLUDED.gate_status,
    decision = EXCLUDED.decision,
    is_hard_gate = EXCLUDED.is_hard_gate,
    stop_reason = EXCLUDED.stop_reason,
    evidence = EXCLUDED.evidence,
    reviewed_by = EXCLUDED.reviewed_by,
    updated_at = NOW();
