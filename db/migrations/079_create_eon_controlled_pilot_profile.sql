-- EON-CONTROLLED-PILOT-INGESTION-001
--
-- Creates one inactive, one-record SuccessFactors pilot profile plus its active
-- Data term. The normal ingestion scheduler reads active profiles only, so this
-- migration cannot schedule or activate E.ON collection.
--
-- The profile is consumed only by the explicit one-shot pilot runner. Productive
-- activation requires a separate controlled gate slice.

WITH pilot_profile AS (
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
        'eon_successfactors_data_controlled_pilot',
        'successfactors:eon_germany',
        'Data',
        NULL,
        NULL,
        1,
        1,
        FALSE
    WHERE NOT EXISTS (
        SELECT 1
        FROM search_profiles
        WHERE profile_name = 'eon_successfactors_data_controlled_pilot'
    )
    RETURNING id
), profile_ref AS (
    SELECT id
    FROM pilot_profile
    UNION ALL
    SELECT id
    FROM search_profiles
    WHERE profile_name = 'eon_successfactors_data_controlled_pilot'
    LIMIT 1
)
INSERT INTO search_terms (
    search_profile_id,
    search_term,
    is_active
)
SELECT
    profile_ref.id,
    'Data',
    TRUE
FROM profile_ref
WHERE NOT EXISTS (
    SELECT 1
    FROM search_terms existing
    WHERE existing.search_profile_id = profile_ref.id
      AND lower(existing.search_term) = lower('Data')
);
