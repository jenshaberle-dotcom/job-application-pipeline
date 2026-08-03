-- STEPSTONE-BASELINE-RUNTIME-001
-- Activate a fail-closed production mode for one bounded unfiltered StepStone
-- page-one census per run while multi-NOT query transport remains unvalidated.
--
-- This migration adds activation and candidate-persistence audit state only.
-- It performs no network request, creates no candidate by itself, activates no
-- connector/source, writes no Bronze/Silver rows and changes no scheduler.

CREATE TABLE IF NOT EXISTS stepstone_runtime_activations (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL DEFAULT 'stepstone',
    search_profile_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    search_location TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'paused',
    control_mode TEXT NOT NULL DEFAULT 'decoupled_baseline_filter',
    baseline_refresh_interval_hours INTEGER NOT NULL,
    max_filtered_runs_between_baselines INTEGER NOT NULL,
    vocabulary_staleness_hours INTEGER NOT NULL,
    origin_refresh_cooldown_hours INTEGER NOT NULL,
    requested_filter_count INTEGER NOT NULL,
    dominance_min_cards INTEGER NOT NULL,
    dominance_min_share NUMERIC(8, 6) NOT NULL,
    validated_transport_name TEXT,
    transport_status TEXT NOT NULL DEFAULT 'unvalidated',
    approved_max_filter_count INTEGER,
    policy_version TEXT NOT NULL,
    activation_reason TEXT NOT NULL,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    paused_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stepstone_runtime_activation_scope UNIQUE (
        source_name,
        search_profile_name,
        search_term,
        search_location
    ),
    CONSTRAINT chk_stepstone_runtime_activation_status CHECK (
        status IN (
            'paused',
            'baseline_only_active',
            'full_cycle_candidate',
            'full_cycle_active'
        )
    ),
    CONSTRAINT chk_stepstone_runtime_activation_control CHECK (
        control_mode = 'decoupled_baseline_filter'
    ),
    CONSTRAINT chk_stepstone_runtime_activation_transport CHECK (
        transport_status IN ('unvalidated', 'candidate', 'validated')
    ),
    CONSTRAINT chk_stepstone_runtime_activation_values CHECK (
        baseline_refresh_interval_hours >= 1
        AND max_filtered_runs_between_baselines >= 1
        AND vocabulary_staleness_hours >= 1
        AND origin_refresh_cooldown_hours >= 0
        AND requested_filter_count >= 1
        AND dominance_min_cards >= 1
        AND dominance_min_share > 0
        AND dominance_min_share <= 1
        AND (
            approved_max_filter_count IS NULL
            OR approved_max_filter_count >= 1
        )
    ),
    CONSTRAINT chk_stepstone_runtime_activation_approval CHECK (
        status = 'paused'
        OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
    ),
    CONSTRAINT chk_stepstone_full_cycle_activation_gate CHECK (
        status <> 'full_cycle_active'
        OR (
            validated_transport_name IS NOT NULL
            AND transport_status = 'validated'
            AND approved_max_filter_count IS NOT NULL
            AND approved_max_filter_count = requested_filter_count
        )
    ),
    CONSTRAINT chk_stepstone_baseline_only_fail_closed CHECK (
        status <> 'baseline_only_active'
        OR transport_status IN ('unvalidated', 'candidate', 'validated')
    )
);

CREATE INDEX IF NOT EXISTS idx_stepstone_runtime_activations_status
    ON stepstone_runtime_activations (
        status,
        search_profile_name,
        search_term
    );

CREATE TABLE IF NOT EXISTS stepstone_candidate_persistence_events (
    id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL
        REFERENCES stepstone_company_discovery_cycle_reviews(id)
        ON DELETE CASCADE,
    review_item_id BIGINT
        REFERENCES stepstone_company_discovery_cycle_items(id)
        ON DELETE SET NULL,
    source_name TEXT NOT NULL DEFAULT 'stepstone',
    search_profile_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    source_mode TEXT NOT NULL,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    evidence_count INTEGER NOT NULL,
    sample_titles JSONB NOT NULL DEFAULT '[]'::jsonb,
    candidate_id BIGINT
        REFERENCES employer_origin_source_candidates(id)
        ON DELETE SET NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL,
    persisted_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stepstone_candidate_persistence_event UNIQUE (
        review_id,
        company_key
    ),
    CONSTRAINT chk_stepstone_candidate_persistence_source_mode CHECK (
        source_mode IN ('baseline', 'filtered', 'backfill')
    ),
    CONSTRAINT chk_stepstone_candidate_persistence_action CHECK (
        action IN (
            'created_discovery_candidate',
            'matched_existing_candidate',
            'skipped_invalid_company'
        )
    ),
    CONSTRAINT chk_stepstone_candidate_persistence_values CHECK (
        evidence_count >= 0
        AND jsonb_typeof(sample_titles) = 'array'
    ),
    CONSTRAINT chk_stepstone_candidate_persistence_candidate CHECK (
        action = 'skipped_invalid_company'
        OR candidate_id IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_stepstone_candidate_persistence_company
    ON stepstone_candidate_persistence_events (
        company_key,
        created_at DESC
    );

CREATE OR REPLACE VIEW gold_stepstone_runtime_activation AS
SELECT
    a.source_name,
    a.search_profile_name,
    a.search_term,
    a.search_location,
    a.status,
    a.control_mode,
    a.baseline_refresh_interval_hours,
    a.max_filtered_runs_between_baselines,
    a.vocabulary_staleness_hours,
    a.origin_refresh_cooldown_hours,
    a.requested_filter_count,
    a.dominance_min_cards,
    a.dominance_min_share,
    a.validated_transport_name,
    a.transport_status,
    a.approved_max_filter_count,
    CASE
        WHEN a.status = 'baseline_only_active'
        THEN 'ready_for_one_page_baseline_run'
        WHEN a.status = 'full_cycle_active'
         AND a.transport_status = 'validated'
         AND a.approved_max_filter_count = a.requested_filter_count
        THEN 'ready_for_decoupled_baseline_and_filtered_runs'
        WHEN a.status = 'full_cycle_candidate'
        THEN 'blocked_pending_transport_or_capacity_approval'
        ELSE 'paused'
    END AS runtime_readiness,
    a.policy_version,
    a.activation_reason,
    a.approved_by,
    a.approved_at,
    a.updated_at
FROM stepstone_runtime_activations a;

CREATE OR REPLACE VIEW gold_stepstone_candidate_persistence_summary AS
SELECT
    source_name,
    search_profile_name,
    search_term,
    company_key,
    max(company_name) AS company_name,
    count(*) AS persisted_review_count,
    sum(evidence_count) AS total_observation_count,
    count(*) FILTER (
        WHERE action = 'created_discovery_candidate'
    ) AS creation_event_count,
    count(*) FILTER (
        WHERE action = 'matched_existing_candidate'
    ) AS existing_match_event_count,
    max(candidate_id) AS candidate_id,
    min(created_at) AS first_persisted_at,
    max(created_at) AS last_persisted_at
FROM stepstone_candidate_persistence_events
WHERE action <> 'skipped_invalid_company'
GROUP BY
    source_name,
    search_profile_name,
    search_term,
    company_key;
