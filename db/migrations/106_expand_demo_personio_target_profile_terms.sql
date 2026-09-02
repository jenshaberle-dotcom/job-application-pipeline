-- DEMO-001 / Product V1 target-profile expansion.
--
-- The two already-authorized Personio Employer-Origin profiles predate the current
-- career-path decision and keep historical `data_engineer` names for stable identity.
-- Their active terms, however, must cover the current target profile:
-- Machine Learning Engineering + Data Engineering + MLOps / AI Reliability.
--
-- Forward-only: do not modify migration 016. Existing Data/Analytics terms remain
-- active; this migration only adds the missing target-role terms.

INSERT INTO search_terms (
    search_profile_id,
    search_term,
    is_active
)
SELECT
    profile.id,
    terms.search_term,
    TRUE
FROM search_profiles AS profile
JOIN (
    VALUES
        ('personio_eraneos_data_engineer_remote', 'Machine Learning Engineer'),
        ('personio_eraneos_data_engineer_remote', 'ML Engineer'),
        ('personio_eraneos_data_engineer_remote', 'MLOps Engineer'),
        ('personio_eraneos_data_engineer_remote', 'ML Platform Engineer'),
        ('personio_eraneos_data_engineer_remote', 'AI Platform Engineer'),
        ('personio_eraneos_data_engineer_remote', 'AI Engineer'),
        ('personio_eraneos_data_engineer_remote', 'AI Reliability Engineer'),
        ('personio_eraneos_data_engineer_remote', 'ML Reliability Engineer'),
        ('personio_eraneos_data_engineer_remote', 'Data Reliability Engineer'),
        ('personio_1komma5grad_data_engineer_germany', 'Machine Learning Engineer'),
        ('personio_1komma5grad_data_engineer_germany', 'ML Engineer'),
        ('personio_1komma5grad_data_engineer_germany', 'MLOps Engineer'),
        ('personio_1komma5grad_data_engineer_germany', 'ML Platform Engineer'),
        ('personio_1komma5grad_data_engineer_germany', 'AI Platform Engineer'),
        ('personio_1komma5grad_data_engineer_germany', 'AI Engineer'),
        ('personio_1komma5grad_data_engineer_germany', 'AI Reliability Engineer'),
        ('personio_1komma5grad_data_engineer_germany', 'ML Reliability Engineer'),
        ('personio_1komma5grad_data_engineer_germany', 'Data Reliability Engineer')
) AS terms(profile_name, search_term)
    ON terms.profile_name = profile.profile_name
ON CONFLICT (search_profile_id, search_term)
DO UPDATE SET
    is_active = EXCLUDED.is_active;
