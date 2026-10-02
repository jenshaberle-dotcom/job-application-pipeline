-- SEARCH-COVERAGE-ADJACENT-ROLES-001
-- Expand the existing market-sensor discovery raster with adjacent role families
-- requested for broader job discovery.
--
-- Search terms are acquisition hints only. Existing relevance, hard-filter and
-- Product gates remain authoritative; this migration does not activate new
-- sources, connectors, schedules or Employer-Origin profiles.

WITH target_profiles(profile_name) AS (
    VALUES
        ('ba_data_engineer_30629_50km'),
        ('ba_data_engineering_remote_nationwide_review'),
        ('stepstone_data_engineer_hannover')
),
terms(search_term) AS (
    VALUES
        -- Product ownership family
        ('Product Owner'),
        ('Technical Product Owner'),
        ('Productowner'),

        -- Systems engineering family
        ('System Engineer'),
        ('Systems Engineer'),
        ('Systemingenieur'),
        ('IT System Engineer'),
        ('IT-Systemingenieur')
)
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
JOIN target_profiles target
  ON target.profile_name = sp.profile_name
CROSS JOIN terms
ON CONFLICT (search_profile_id, search_term)
DO UPDATE SET is_active = TRUE;
