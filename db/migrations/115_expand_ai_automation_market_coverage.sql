-- MARKET-PARITY-001
-- Expand the generic AI/automation discovery raster and seed one first-party
-- Employer-Origin candidate from current public market evidence.
--
-- This migration does not directly activate an Employer-Origin source and does
-- not write Bronze/Silver/Gold. The canonical generic proof=PASS product remains
-- the sole activation authority.

WITH target_profiles(profile_name) AS (
    VALUES
        ('ba_data_engineer_30629_50km'),
        ('stepstone_data_engineer_hannover')
),
terms(search_term) AS (
    VALUES
        ('AI Architect'),
        ('AI Automation'),
        ('AI Automation Architect'),
        ('Agentic AI'),
        ('AI Governance')
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

INSERT INTO employer_origin_source_candidates (
    company_key,
    company_name,
    candidate_url,
    source_name_candidate,
    source_family_candidate,
    source_target_candidate,
    source_type_candidate,
    status,
    risk_level,
    notes,
    updated_at
)
SELECT
    'hornetsecurity',
    'Hornetsecurity GmbH',
    'https://www.hornetsecurity.com/en/career/',
    'generic_origin:hornetsecurity',
    'generic_origin',
    'hornetsecurity',
    'employer_origin_career_site',
    'discovery',
    'low',
    (
        'Seeded from current public market-sensor evidence and the official '
        'first-party career origin for market coverage parity. Admission and '
        'recurring activation remain governed exclusively by canonical generic proof=PASS.'
    ),
    now()
WHERE NOT EXISTS (
    SELECT 1
    FROM employer_origin_source_candidates
    WHERE company_key = 'hornetsecurity'
      AND candidate_url = 'https://www.hornetsecurity.com/en/career/'
);
