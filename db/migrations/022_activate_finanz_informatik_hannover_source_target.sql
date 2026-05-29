-- S2P controlled Finanz Informatik Hannover source-target activation.
--
-- This migration intentionally activates exactly one bounded source target:
--   source_name = 'finanz_informatik:hannover'
--
-- It does not approve broad Finanz Informatik crawling, all-location ingestion,
-- CSV/export-based activation gates, or source-family-wide collection. The
-- connector itself remains request-bounded and relevance-gated.
--
-- Schema note:
-- - search_profiles.offer_type is currently an integer-coded field; this
--   migration keeps the existing default semantics by writing 1 explicitly.
-- - search_terms references search_profiles via search_profile_id.

insert into search_profiles (
    profile_name,
    source_name,
    search_location,
    search_radius_km,
    offer_type,
    page_size,
    is_active
)
select
    'finanz_informatik_hannover_precision',
    'finanz_informatik:hannover',
    'Hannover',
    50,
    1,
    3,
    true
where not exists (
    select 1
    from search_profiles
    where profile_name = 'finanz_informatik_hannover_precision'
);

with active_profile as (
    select id
    from search_profiles
    where profile_name = 'finanz_informatik_hannover_precision'
), desired_terms(search_term) as (
    values
        ('Data'),
        ('Daten'),
        ('Analytics'),
        ('Business Intelligence'),
        ('BI'),
        ('SQL'),
        ('Python'),
        ('KI'),
        ('AI'),
        ('Software'),
        ('Entwickler'),
        ('JavaScript'),
        ('UI'),
        ('Product Owner'),
        ('Business Analyst')
)
insert into search_terms (search_profile_id, search_term, is_active)
select active_profile.id, desired_terms.search_term, true
from active_profile
cross join desired_terms
where not exists (
    select 1
    from search_terms existing
    where existing.search_profile_id = active_profile.id
      and lower(existing.search_term) = lower(desired_terms.search_term)
);
