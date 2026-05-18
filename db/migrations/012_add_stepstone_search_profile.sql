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
WHERE sp.profile_name = 'stepstone_data_engineer_hannover'
ON CONFLICT (search_profile_id, search_term)
DO UPDATE SET
    is_active = EXCLUDED.is_active;
