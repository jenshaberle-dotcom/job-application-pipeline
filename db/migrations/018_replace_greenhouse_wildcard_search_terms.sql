-- Replace the Greenhouse wildcard search term with explicit local matching terms.
--
-- Context:
-- Greenhouse boards are fetched as full source targets and filtered locally.
-- A wildcard search term (`*`) turns the board into an unfiltered snapshot and
-- produces too many irrelevant default-ingestion results.
--
-- This migration keeps the existing greenhouse_stripe profile but replaces the
-- active wildcard search intent with explicit Data/Analytics-oriented terms.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM search_profiles
        WHERE profile_name = 'greenhouse_stripe'
          AND source_name = 'greenhouse:stripe'
    ) THEN
        RAISE EXCEPTION 'Expected active Greenhouse profile not found: greenhouse_stripe / greenhouse:stripe';
    END IF;
END $$;

WITH target_profile AS (
    SELECT id
    FROM search_profiles
    WHERE profile_name = 'greenhouse_stripe'
      AND source_name = 'greenhouse:stripe'
)
UPDATE search_terms st
SET is_active = false
FROM target_profile tp
WHERE st.search_profile_id = tp.id
  AND st.search_term = '*';

WITH target_profile AS (
    SELECT id
    FROM search_profiles
    WHERE profile_name = 'greenhouse_stripe'
      AND source_name = 'greenhouse:stripe'
),
desired_terms(search_term) AS (
    VALUES
        ('Data Engineer'),
        ('Analytics Engineer'),
        ('ETL'),
        ('Data Platform'),
        ('Data Warehouse'),
        ('Big Data'),
        ('Python SQL')
)
INSERT INTO search_terms (
    search_profile_id,
    search_term,
    is_active
)
SELECT
    tp.id,
    dt.search_term,
    true
FROM target_profile tp
CROSS JOIN desired_terms dt
WHERE NOT EXISTS (
    SELECT 1
    FROM search_terms st
    WHERE st.search_profile_id = tp.id
      AND st.search_term = dt.search_term
);

WITH target_profile AS (
    SELECT id
    FROM search_profiles
    WHERE profile_name = 'greenhouse_stripe'
      AND source_name = 'greenhouse:stripe'
),
desired_terms(search_term) AS (
    VALUES
        ('Data Engineer'),
        ('Analytics Engineer'),
        ('ETL'),
        ('Data Platform'),
        ('Data Warehouse'),
        ('Big Data'),
        ('Python SQL')
)
UPDATE search_terms st
SET is_active = true
FROM target_profile tp, desired_terms dt
WHERE st.search_profile_id = tp.id
  AND st.search_term = dt.search_term;

COMMIT;
