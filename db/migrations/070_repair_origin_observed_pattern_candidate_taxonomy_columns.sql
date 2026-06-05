-- 070_repair_origin_observed_pattern_candidate_taxonomy_columns.sql
--
-- Repair migration after A2D2/A2E taxonomy hardening.
-- Migration 069 may be tracked already, while origin_observed_pattern_candidates
-- still lacks the taxonomy columns required by the promotion agent.
-- This migration is intentionally idempotent.

ALTER TABLE origin_observed_pattern_candidates
ADD COLUMN IF NOT EXISTS pattern_category text;

ALTER TABLE origin_observed_pattern_candidates
ADD COLUMN IF NOT EXISTS usage_scope text;

CREATE OR REPLACE VIEW gold_origin_promoted_observation_patterns AS
SELECT
    pattern_type,
    pattern_value,
    evidence_count,
    confidence,
    promotion_status,
    evidence,
    updated_at,
    pattern_category,
    usage_scope
FROM origin_observed_pattern_candidates
WHERE promotion_status = 'promoted';
