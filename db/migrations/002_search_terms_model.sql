CREATE TABLE IF NOT EXISTS search_terms (
    id BIGSERIAL PRIMARY KEY,
    search_profile_id BIGINT NOT NULL REFERENCES search_profiles(id),
    search_term TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (search_profile_id, search_term)
);

INSERT INTO search_terms (
    search_profile_id,
    search_term
)
SELECT
    id,
    search_term
FROM search_profiles
WHERE profile_name = 'ba_data_engineer_30629_50km'
ON CONFLICT (search_profile_id, search_term) DO NOTHING;

INSERT INTO search_terms (
    search_profile_id,
    search_term
)
SELECT
    id,
    term
FROM search_profiles
CROSS JOIN (
    VALUES
        ('Analytics Engineer'),
        ('ETL'),
        ('Data Platform'),
        ('Data Warehouse'),
        ('Big Data'),
        ('Python SQL')
) AS terms(term)
WHERE profile_name = 'ba_data_engineer_30629_50km'
ON CONFLICT (search_profile_id, search_term) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_search_terms_profile_id
ON search_terms (search_profile_id);

CREATE INDEX IF NOT EXISTS idx_search_terms_active
ON search_terms (is_active);
