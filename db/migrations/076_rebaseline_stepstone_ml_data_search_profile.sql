-- PROFILE-SEARCH-001
-- Rebaseline the active StepStone search raster after the operator's switch
-- to the Machine Learning Engineer profile with a strong Data Engineering
-- and Reliability focus.
--
-- The existing profile identifier is retained for compatibility with current
-- runtime commands and tests. Its product meaning changes from Data-first to
-- ML-first. A later identifier rename may be handled as a separate compatibility
-- refactor.
--
-- This migration changes repository/database configuration only. It does not
-- run StepStone, create candidates, activate connectors or mutate schedulers.

INSERT INTO search_profiles (
    profile_name,
    source_name,
    search_term,
    search_location,
    search_radius_km,
    offer_type,
    page_size,
    is_active
)
VALUES (
    'stepstone_data_engineer_hannover',
    'stepstone',
    NULL,
    'Hannover',
    NULL,
    NULL,
    25,
    TRUE
)
ON CONFLICT (profile_name)
DO UPDATE SET
    source_name = EXCLUDED.source_name,
    search_term = EXCLUDED.search_term,
    search_location = EXCLUDED.search_location,
    search_radius_km = EXCLUDED.search_radius_km,
    offer_type = EXCLUDED.offer_type,
    page_size = EXCLUDED.page_size,
    is_active = EXCLUDED.is_active;

-- Re-running the migration keeps the configured raster exact: terms removed
-- from the approved profile are disabled before the active set is restored.
UPDATE search_terms st
SET is_active = FALSE
FROM search_profiles sp
WHERE st.search_profile_id = sp.id
  AND sp.profile_name = 'stepstone_data_engineer_hannover';

INSERT INTO search_terms (
    search_profile_id,
    search_term,
    is_active
)
SELECT
    sp.id,
    terms.search_term,
    TRUE
FROM search_profiles sp
CROSS JOIN (
    VALUES
        -- Primary Machine Learning Engineering family
        ('Machine Learning Engineer'),
        ('ML Engineer'),
        ('MLOps Engineer'),
        ('ML Platform Engineer'),
        ('AI Platform Engineer'),
        ('AI Engineer'),

        -- Strong Data Engineering bridge and data-centric ML focus
        ('Data Engineer'),
        ('Data Platform Engineer'),
        ('Analytics Engineer'),

        -- Strategic Reliability specialization probes
        ('AI Reliability Engineer'),
        ('ML Reliability Engineer'),

        -- Broad supporting discovery term
        ('Machine Learning')
) AS terms(search_term)
WHERE sp.profile_name = 'stepstone_data_engineer_hannover'
ON CONFLICT (search_profile_id, search_term)
DO UPDATE SET
    is_active = EXCLUDED.is_active;

-- Intentionally not carried forward as standalone active search terms:
-- ETL, Data Warehouse, Big Data and Python SQL.
-- They remain relevant matching/skill signals but are too Data-Engineer-first
-- or too broad/noisy to define the canonical ML-first discovery raster.
--
-- Existing StepStone NOT-wave validation remains limited to Data Engineer and
-- Analytics Engineer until the ML-first terms receive their own stability probes.
