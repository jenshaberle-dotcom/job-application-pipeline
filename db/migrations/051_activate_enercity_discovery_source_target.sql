-- S7V controlled enercity source-target activation.
--
-- This migration intentionally activates exactly one bounded source target:
--   source_name = 'enercity:discovery'
--
-- Preconditions documented in prior gates:
-- - connector_validation_gate passed with ready_for_final_approval
-- - final_approval_gate passed with approve_connector_registration
-- - S7U activation readiness supported activation with non_job_preview_count = 0
--
-- Boundary:
-- - This migration creates one active search profile and bounded active search terms.
-- - It does not run ingestion, write Bronze records, create scheduler changes,
--   activate a source family, or use CSV/Excel/export artifacts as inputs.
--
-- Schema note:
-- - search_profiles.offer_type is currently an integer-coded field; this
--   migration keeps the existing default semantics by writing 1 explicitly.
-- - search_terms references search_profiles via search_profile_id.

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
    'enercity_discovery_hannover_precision',
    'enercity:discovery',
    'Hannover',
    50,
    1,
    3,
    true
WHERE NOT EXISTS (
    SELECT 1
    FROM search_profiles
    WHERE profile_name = 'enercity_discovery_hannover_precision'
);

WITH active_profile AS (
    SELECT id
    FROM search_profiles
    WHERE profile_name = 'enercity_discovery_hannover_precision'
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
