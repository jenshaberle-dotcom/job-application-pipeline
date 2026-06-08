-- SENSOR-001C BA Remote/Nationwide Controlled Activation
--
-- This migration creates a review-controlled BA remote/nationwide profile, but
-- intentionally keeps it inactive. It does not run ingestion, does not change the
-- scheduler, and does not modify the existing Hannover/50km BA profile.
--
-- The profile is a DB-backed review object for the next gated step. Productive
-- activation requires a later explicit approval step.

WITH review_profile AS (
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
    SELECT
        'ba_data_engineering_remote_nationwide_review',
        'bundesagentur_fuer_arbeit',
        'Data Engineer',
        NULL,
        NULL,
        1,
        10,
        FALSE
    WHERE NOT EXISTS (
        SELECT 1
        FROM search_profiles
        WHERE profile_name = 'ba_data_engineering_remote_nationwide_review'
    )
    RETURNING id
),
profile_ref AS (
    SELECT id FROM review_profile
    UNION ALL
    SELECT id
    FROM search_profiles
    WHERE profile_name = 'ba_data_engineering_remote_nationwide_review'
    LIMIT 1
),
terms(search_term) AS (
    VALUES
        ('Data Engineer'),
        ('Analytics Engineer'),
        ('Big Data'),
        ('Data Platform'),
        ('Data Warehouse'),
        ('ETL'),
        ('Python SQL')
)
INSERT INTO search_terms (
    search_profile_id,
    search_term,
    is_active
)
SELECT
    profile_ref.id,
    terms.search_term,
    TRUE
FROM profile_ref
CROSS JOIN terms
WHERE NOT EXISTS (
    SELECT 1
    FROM search_terms existing
    WHERE existing.search_profile_id = profile_ref.id
      AND lower(existing.search_term) = lower(terms.search_term)
);
