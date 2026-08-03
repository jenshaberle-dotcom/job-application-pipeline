-- STEPSTONE-BASELINE-REVIEW-ACTION-HOTFIX-001
-- Align the persisted StepStone review action contract with the activated
-- baseline-only production runner introduced in migration 082.
--
-- Forward-only schema repair: historical migrations remain checksum-stable.
-- This migration performs no network request, candidate creation, connector or
-- source activation, scheduler mutation, provider call or application action.

ALTER TABLE stepstone_company_discovery_cycle_reviews
DROP CONSTRAINT IF EXISTS chk_stepstone_company_cycle_action;

ALTER TABLE stepstone_company_discovery_cycle_reviews
ADD CONSTRAINT chk_stepstone_company_cycle_action CHECK (
    action IN (
        'run_baseline_only',
        'run_baseline_learning',
        'run_fetch_time_company_not_probe',
        'skip_empty_exclusion_wave',
        'run_production_baseline_census'
    )
);
