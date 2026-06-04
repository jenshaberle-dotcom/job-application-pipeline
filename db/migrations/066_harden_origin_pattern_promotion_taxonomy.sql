-- A2D2: harden origin pattern promotion taxonomy.
--
-- Promotion remains learning/pipeline-strategy input only. This migration adds
-- explicit semantic categories and usage scopes so URL, provider, profile,
-- location and remote/flexibility signals are not mixed in a flat pattern list.

ALTER TABLE origin_observed_pattern_candidates
ADD COLUMN IF NOT EXISTS pattern_category TEXT NOT NULL DEFAULT 'unclassified',
ADD COLUMN IF NOT EXISTS usage_scope TEXT NOT NULL DEFAULT 'diagnostics_only';

ALTER TABLE origin_pattern_promotion_decisions
ADD COLUMN IF NOT EXISTS pattern_category TEXT NOT NULL DEFAULT 'unclassified',
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
        'profile_supporting_signal',
        'profile_ambiguous_signal',
        'profile_signal_candidate',
        'structural_marker',
        'unclassified_candidate',
        'diagnostics_only'
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

-- Repair the known flat-taxonomy weakness from A2D if that promotion already ran locally.
UPDATE origin_observed_pattern_candidates
SET promotion_status = 'candidate',
    pattern_category = 'location_multi_signal',
    usage_scope = 'diagnostics_only',
    learning_notes = concat_ws(' ', nullif(learning_notes, ''), 'A2D2 taxonomy hardening: multi-location wording is not a remote-work signal.'),
    updated_at = now()
WHERE pattern_type = 'remote_signal'
  AND lower(pattern_value) IN ('+ weitere', '+ weitere standorte');

UPDATE origin_observed_pattern_candidates
SET promotion_status = 'candidate',
    pattern_category = 'profile_ambiguous_signal',
    usage_scope = 'diagnostics_only',
    learning_notes = concat_ws(' ', nullif(learning_notes, ''), 'A2D2 taxonomy hardening: short ambiguous profile signal requires more context.'),
    updated_at = now()
WHERE pattern_type = 'profile_signal'
  AND lower(pattern_value) = 'bi';

CREATE INDEX IF NOT EXISTS idx_origin_observed_pattern_candidates_usage_scope
    ON origin_observed_pattern_candidates (promotion_status, pattern_category, usage_scope);

CREATE INDEX IF NOT EXISTS idx_origin_pattern_promotion_decisions_usage_scope
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
