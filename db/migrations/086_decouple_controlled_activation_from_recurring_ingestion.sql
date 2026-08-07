-- PRODUCT-V1-CONTROLLED-ACTIVATION-CAP / Issue #415
--
-- Separate controlled source activation from recurring-ingestion eligibility.
-- Existing profiles preserve their current recurring behavior through the TRUE
-- default. New A1-controlled profiles can be active while remaining excluded
-- from unscoped/daily ingestion.
--
-- This migration does not activate any source, create any profile, run ingestion,
-- change scheduler configuration, call a provider, rank jobs or touch applications.

ALTER TABLE search_profiles
ADD COLUMN IF NOT EXISTS recurring_ingestion_enabled BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_search_profiles_recurring_active
ON search_profiles (source_name, profile_name)
WHERE is_active = TRUE
  AND recurring_ingestion_enabled = TRUE;

COMMENT ON COLUMN search_profiles.recurring_ingestion_enabled IS
'Whether an active profile may be selected by unscoped/source-family recurring ingestion. Exact explicit profile execution remains separately operator/automation controlled.';
