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
    'personio_schluetersche_data_engineer_hannover',
    'personio:schluetersche-mediengruppe',
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

INSERT INTO search_terms (
    search_profile_id,
    search_term,
    is_active
)
SELECT
    sp.id,
    'Data Engineer',
    TRUE
FROM search_profiles sp
WHERE sp.profile_name = 'personio_schluetersche_data_engineer_hannover'
ON CONFLICT (search_profile_id, search_term)
DO UPDATE SET
    is_active = EXCLUDED.is_active;
