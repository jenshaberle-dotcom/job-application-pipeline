-- 069_repair_origin_observed_pattern_taxonomy_columns.sql
--
-- Repair and harden A2D2/A2E promotion taxonomy storage.
-- Context:
-- Some local DBs may have migration 066 tracked while the expected taxonomy
-- columns only exist on origin_pattern_promotion_decisions, not on
-- origin_observed_pattern_candidates. The promotion agent updates both tables.
-- This migration is intentionally idempotent and also adds the cleaner
-- profile_domain_signal taxonomy category introduced after A2D2 review.

ALTER TABLE origin_observed_pattern_candidates
ADD COLUMN IF NOT EXISTS pattern_category TEXT NOT NULL DEFAULT 'unclassified';

ALTER TABLE origin_observed_pattern_candidates
ADD COLUMN IF NOT EXISTS usage_scope TEXT NOT NULL DEFAULT 'diagnostics_only';

ALTER TABLE origin_pattern_promotion_decisions
ADD COLUMN IF NOT EXISTS pattern_category TEXT NOT NULL DEFAULT 'unclassified';

ALTER TABLE origin_pattern_promotion_decisions
ADD COLUMN IF NOT EXISTS usage_scope TEXT NOT NULL DEFAULT 'diagnostics_only';

ALTER TABLE origin_observed_pattern_candidates
DROP CONSTRAINT IF EXISTS chk_origin_observed_pattern_candidates_pattern_category;

ALTER TABLE origin_observed_pattern_candidates
ADD CONSTRAINT chk_origin_observed_pattern_candidates_pattern_category
CHECK (
    pattern_category IN (
        'unclassified',
        'url_detail_pattern',
        'url_listing_pattern',
        'url_pattern_candidate',
        'ats_family',
        'ats_family_candidate',
        'structured_jobposting_marker',
        'structured_marker_candidate',
        'location_exact_signal',
        'location_germany_wide_signal',
        'location_multi_signal',
        'location_signal_candidate',
        'remote_work_signal',
        'remote_signal_candidate',
        'profile_role_signal',
        'profile_skill_signal',
        'profile_domain_signal',
        'profile_supporting_signal',
        'profile_ambiguous_signal',
        'profile_signal_candidate',
        'structural_marker',
        'unclassified_candidate',
        'diagnostics_only'
    )
);

ALTER TABLE origin_pattern_promotion_decisions
DROP CONSTRAINT IF EXISTS chk_origin_pattern_promotion_decisions_pattern_category;

ALTER TABLE origin_pattern_promotion_decisions
ADD CONSTRAINT chk_origin_pattern_promotion_decisions_pattern_category
CHECK (
    pattern_category IN (
        'unclassified',
        'url_detail_pattern',
        'url_listing_pattern',
        'url_pattern_candidate',
        'ats_family',
        'ats_family_candidate',
        'structured_jobposting_marker',
        'structured_marker_candidate',
        'location_exact_signal',
        'location_germany_wide_signal',
        'location_multi_signal',
        'location_signal_candidate',
        'remote_work_signal',
        'remote_signal_candidate',
        'profile_role_signal',
        'profile_skill_signal',
        'profile_domain_signal',
        'profile_supporting_signal',
        'profile_ambiguous_signal',
        'profile_signal_candidate',
        'structural_marker',
        'unclassified_candidate',
        'diagnostics_only'
    )
);

ALTER TABLE origin_observed_pattern_candidates
DROP CONSTRAINT IF EXISTS chk_origin_observed_pattern_candidates_usage_scope;

ALTER TABLE origin_observed_pattern_candidates
ADD CONSTRAINT chk_origin_observed_pattern_candidates_usage_scope
CHECK (
    usage_scope IN (
        'diagnostics_only',
        'url_finder_strategy',
        'detail_url_discovery',
        'listing_url_discovery',
        'relevance_profile',
        'relevance_location',
        'relevance_remote'
    )
);

ALTER TABLE origin_pattern_promotion_decisions
DROP CONSTRAINT IF EXISTS chk_origin_pattern_promotion_decisions_usage_scope;

ALTER TABLE origin_pattern_promotion_decisions
ADD CONSTRAINT chk_origin_pattern_promotion_decisions_usage_scope
CHECK (
    usage_scope IN (
        'diagnostics_only',
        'url_finder_strategy',
        'detail_url_discovery',
        'listing_url_discovery',
        'relevance_profile',
        'relevance_location',
        'relevance_remote'
    )
);

-- Repair already-observed candidates from earlier flat-taxonomy runs.
UPDATE origin_observed_pattern_candidates
SET promotion_status = 'candidate',
    pattern_category = 'location_multi_signal',
    usage_scope = 'diagnostics_only',
    learning_notes = concat_ws(' ', nullif(learning_notes, ''), 'A2D2/A2E taxonomy repair: multi-location wording is not a remote-work signal.'),
    updated_at = now()
WHERE pattern_type = 'remote_signal'
  AND lower(pattern_value) IN ('+ weitere', '+ weitere standorte');

UPDATE origin_observed_pattern_candidates
SET promotion_status = 'candidate',
    pattern_category = 'profile_ambiguous_signal',
    usage_scope = 'diagnostics_only',
    learning_notes = concat_ws(' ', nullif(learning_notes, ''), 'A2D2/A2E taxonomy repair: short ambiguous profile signal requires more context.'),
    updated_at = now()
WHERE pattern_type = 'profile_signal'
  AND lower(pattern_value) = 'bi';

UPDATE origin_observed_pattern_candidates
SET pattern_category = 'profile_domain_signal',
    usage_scope = 'relevance_profile',
    learning_notes = concat_ws(' ', nullif(learning_notes, ''), 'A2E taxonomy repair: domain wording is profile-domain evidence, not a single skill.'),
    updated_at = now()
WHERE pattern_type = 'profile_signal'
  AND lower(pattern_value) = 'data & analytics'
  AND promotion_status = 'promoted';

UPDATE origin_pattern_promotion_decisions
SET pattern_category = 'profile_domain_signal',
    usage_scope = 'relevance_profile'
WHERE pattern_type = 'profile_signal'
  AND lower(pattern_value) = 'data & analytics'
  AND promotion_status = 'promoted';

UPDATE origin_observed_pattern_candidates
SET usage_scope = 'diagnostics_only',
    learning_notes = concat_ws(' ', nullif(learning_notes, ''), 'A2E taxonomy repair: structural markers are diagnostics only; ATS family and URL patterns carry URL-finder strategy.'),
    updated_at = now()
WHERE pattern_type = 'structural_marker';

UPDATE origin_pattern_promotion_decisions
SET usage_scope = 'diagnostics_only'
WHERE pattern_type = 'structural_marker';

CREATE INDEX IF NOT EXISTS idx_origin_observed_pattern_candidates_taxonomy_usage
    ON origin_observed_pattern_candidates (promotion_status, pattern_category, usage_scope);

CREATE INDEX IF NOT EXISTS idx_origin_pattern_promotion_decisions_taxonomy_usage
    ON origin_pattern_promotion_decisions (promotion_status, pattern_category, usage_scope);

CREATE OR REPLACE VIEW gold_origin_promoted_observation_patterns AS
SELECT
    pattern_type,
    pattern_value,
    pattern_category,
    usage_scope,
    evidence_count,
    confidence,
    promotion_status,
    evidence,
    updated_at
FROM origin_observed_pattern_candidates
WHERE promotion_status = 'promoted';
