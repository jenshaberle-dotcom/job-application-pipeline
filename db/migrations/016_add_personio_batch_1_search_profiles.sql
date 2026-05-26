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
VALUES
    ('personio_eraneos_data_engineer_remote', 'personio:eraneos', NULL, 'remote', NULL, NULL, 50, TRUE),
    ('personio_1komma5grad_data_engineer_germany', 'personio:1komma5grad', NULL, 'Germany', NULL, NULL, 50, TRUE),
    ('personio_itp_data_engineer_hannover', 'personio:it-p', NULL, 'Hannover', NULL, NULL, 25, TRUE),
    ('personio_otl_akademie_data_engineer_remote', 'personio:otl-akademie', NULL, 'remote', NULL, NULL, 25, TRUE)
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
JOIN (
    VALUES
        ('personio_eraneos_data_engineer_remote', 'Data Engineer'),
        ('personio_eraneos_data_engineer_remote', 'Analytics Engineer'),
        ('personio_eraneos_data_engineer_remote', 'Data Platform'),
        ('personio_1komma5grad_data_engineer_germany', 'Data Engineer'),
        ('personio_1komma5grad_data_engineer_germany', 'Analytics Engineer'),
        ('personio_1komma5grad_data_engineer_germany', 'Data Platform'),
        ('personio_itp_data_engineer_hannover', 'Data Engineer'),
        ('personio_itp_data_engineer_hannover', 'Analytics Engineer'),
        ('personio_itp_data_engineer_hannover', 'Data Platform'),
        ('personio_otl_akademie_data_engineer_remote', 'Data Engineer'),
        ('personio_otl_akademie_data_engineer_remote', 'ETL')
) AS terms(profile_name, search_term)
    ON terms.profile_name = sp.profile_name
ON CONFLICT (search_profile_id, search_term)
DO UPDATE SET
    is_active = EXCLUDED.is_active;
