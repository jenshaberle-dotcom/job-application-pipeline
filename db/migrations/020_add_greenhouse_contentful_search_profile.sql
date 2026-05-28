-- Add Contentful as the first controlled Greenhouse S1 expansion target.
--
-- Context:
-- - S1C defensive validation confirmed that the Contentful Greenhouse board is reachable.
-- - The preview returned 89 total jobs and 2 locally matched jobs.
-- - This migration activates only one new Greenhouse board to keep the first
--   source-coverage change measurable and reversible.
-- - Greenhouse does not support server-side keyword filtering in the current
--   connector, so the board is fetched once and filtered locally against the
--   active multi-term search intent.

BEGIN;

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
    'greenhouse_contentful',
    'greenhouse:contentful',
    NULL,
    'global',
    0,
    NULL,
    100,
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
        ('Data Engineer'),
        ('Analytics Engineer'),
        ('ETL'),
        ('Data Platform'),
        ('Data Warehouse'),
        ('Big Data'),
        ('Python SQL')
) AS terms(search_term)
WHERE sp.profile_name = 'greenhouse_contentful'
ON CONFLICT (search_profile_id, search_term)
DO UPDATE SET
    is_active = EXCLUDED.is_active;

COMMIT;
