-- 067_repair_origin_pattern_promotion_taxonomy_columns.sql
--
-- Repair migration for A2D2 taxonomy hardening.
-- Context:
-- Migration tracking may show 066 as applied while the expected taxonomy columns
-- are missing from origin_pattern_promotion_decisions. This migration is
-- intentionally idempotent and only repairs the schema shape expected by the
-- promotion agent.

ALTER TABLE origin_pattern_promotion_decisions
ADD COLUMN IF NOT EXISTS pattern_category text;

ALTER TABLE origin_pattern_promotion_decisions
ADD COLUMN IF NOT EXISTS usage_scope text;
