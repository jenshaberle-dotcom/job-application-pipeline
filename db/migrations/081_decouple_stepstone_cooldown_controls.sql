-- STEPSTONE-DECOUPLED-CYCLE-001
-- Separate baseline cadence, stable company suppression, origin-refresh
-- deduplication and company-title vocabulary freshness.
--
-- Historical migrations 079/080 remain unchanged. Their reselection-cooldown
-- model is retained only as legacy evidence and is no longer sufficient for
-- activation. This migration performs no StepStone request and activates no
-- source, scheduler, provider, candidate or application action.

ALTER TABLE stepstone_dynamic_filter_policy
ADD COLUMN IF NOT EXISTS control_mode TEXT NOT NULL DEFAULT 'legacy_reselection';
ALTER TABLE stepstone_dynamic_filter_policy
ADD COLUMN IF NOT EXISTS suppression_source_mode TEXT;
ALTER TABLE stepstone_dynamic_filter_policy
ADD COLUMN IF NOT EXISTS baseline_refresh_interval_hours INTEGER;
ALTER TABLE stepstone_dynamic_filter_policy
ADD COLUMN IF NOT EXISTS max_filtered_runs_between_baselines INTEGER;
ALTER TABLE stepstone_dynamic_filter_policy
ADD COLUMN IF NOT EXISTS vocabulary_staleness_hours INTEGER;
ALTER TABLE stepstone_dynamic_filter_policy
ADD COLUMN IF NOT EXISTS origin_refresh_cooldown_hours INTEGER;

ALTER TABLE stepstone_dynamic_filter_policy
DROP CONSTRAINT IF EXISTS chk_stepstone_dynamic_filter_control_mode;
ALTER TABLE stepstone_dynamic_filter_policy
ADD CONSTRAINT chk_stepstone_dynamic_filter_control_mode CHECK (
    control_mode IN ('legacy_reselection', 'decoupled_baseline_filter')
);

ALTER TABLE stepstone_dynamic_filter_policy
DROP CONSTRAINT IF EXISTS chk_stepstone_dynamic_filter_suppression_source;
ALTER TABLE stepstone_dynamic_filter_policy
ADD CONSTRAINT chk_stepstone_dynamic_filter_suppression_source CHECK (
    suppression_source_mode IS NULL
    OR suppression_source_mode = 'last_valid_baseline'
);

ALTER TABLE stepstone_dynamic_filter_policy
DROP CONSTRAINT IF EXISTS chk_stepstone_dynamic_filter_decoupled_values;
ALTER TABLE stepstone_dynamic_filter_policy
ADD CONSTRAINT chk_stepstone_dynamic_filter_decoupled_values CHECK (
    (
        baseline_refresh_interval_hours IS NULL
        OR baseline_refresh_interval_hours >= 1
    )
    AND (
        max_filtered_runs_between_baselines IS NULL
        OR max_filtered_runs_between_baselines >= 1
    )
    AND (
        vocabulary_staleness_hours IS NULL
        OR vocabulary_staleness_hours >= 1
    )
    AND (
        origin_refresh_cooldown_hours IS NULL
        OR origin_refresh_cooldown_hours >= 0
    )
);

ALTER TABLE stepstone_dynamic_filter_policy
DROP CONSTRAINT IF EXISTS chk_stepstone_dynamic_filter_policy_approval;
ALTER TABLE stepstone_dynamic_filter_policy
ADD CONSTRAINT chk_stepstone_dynamic_filter_policy_approval CHECK (
    status <> 'approved'
    OR (
        control_mode = 'decoupled_baseline_filter'
        AND suppression_source_mode = 'last_valid_baseline'
        AND requested_filter_count IS NOT NULL
        AND dominance_override_min_cards IS NOT NULL
        AND dominance_override_min_share IS NOT NULL
        AND baseline_refresh_interval_hours IS NOT NULL
        AND max_filtered_runs_between_baselines IS NOT NULL
        AND vocabulary_staleness_hours IS NOT NULL
        AND origin_refresh_cooldown_hours IS NOT NULL
        AND validated_transport_name IS NOT NULL
        AND transport_status = 'validated'
        AND approved_by IS NOT NULL
        AND approved_at IS NOT NULL
    )
);

COMMENT ON COLUMN stepstone_dynamic_filter_policy.reselection_cooldown_hours IS
'Legacy rotation control from migrations 079/080. Not used by the decoupled baseline/filter control mode.';
COMMENT ON COLUMN stepstone_dynamic_filter_policy.baseline_refresh_interval_hours IS
'Minimum/target cadence for the next unfiltered market-census run.';
COMMENT ON COLUMN stepstone_dynamic_filter_policy.origin_refresh_cooldown_hours IS
'Deduplication window for employer-origin connector refresh signals; it never removes a company from the StepStone suppression set.';

CREATE TABLE IF NOT EXISTS stepstone_filter_suppression_sets (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL DEFAULT 'stepstone',
    search_profile_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    baseline_review_id BIGINT
        REFERENCES stepstone_company_discovery_cycle_reviews(id)
        ON DELETE SET NULL,
    baseline_observed_at TIMESTAMPTZ NOT NULL,
    baseline_observed_count INTEGER NOT NULL,
    baseline_distinct_company_count INTEGER NOT NULL,
    requested_filter_count INTEGER NOT NULL,
    selected_filter_count INTEGER NOT NULL,
    transport_name TEXT,
    transport_status TEXT NOT NULL DEFAULT 'unvalidated',
    status TEXT NOT NULL DEFAULT 'diagnostic_only',
    policy_version TEXT NOT NULL,
    activated_at TIMESTAMPTZ,
    superseded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_stepstone_suppression_set_counts CHECK (
        baseline_observed_count >= 0
        AND baseline_distinct_company_count >= 0
        AND requested_filter_count >= 1
        AND selected_filter_count >= 0
        AND selected_filter_count <= requested_filter_count
    ),
    CONSTRAINT chk_stepstone_suppression_set_transport CHECK (
        transport_status IN ('unvalidated', 'candidate', 'validated')
    ),
    CONSTRAINT chk_stepstone_suppression_set_status CHECK (
        status IN ('diagnostic_only', 'candidate', 'active', 'superseded')
    ),
    CONSTRAINT chk_stepstone_suppression_set_activation CHECK (
        status <> 'active'
        OR (
            baseline_review_id IS NOT NULL
            AND selected_filter_count >= 1
            AND transport_name IS NOT NULL
            AND transport_status = 'validated'
            AND activated_at IS NOT NULL
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_stepstone_active_suppression_set_scope
    ON stepstone_filter_suppression_sets (
        source_name,
        search_profile_name,
        search_term
    )
    WHERE status = 'active';

CREATE TABLE IF NOT EXISTS stepstone_filter_suppression_set_items (
    id BIGSERIAL PRIMARY KEY,
    suppression_set_id BIGINT NOT NULL
        REFERENCES stepstone_filter_suppression_sets(id)
        ON DELETE CASCADE,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    filter_alias TEXT NOT NULL,
    baseline_card_count INTEGER NOT NULL,
    baseline_card_share NUMERIC(8, 6) NOT NULL,
    first_position INTEGER NOT NULL,
    selection_rank INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stepstone_suppression_set_item UNIQUE (
        suppression_set_id,
        company_key
    ),
    CONSTRAINT uq_stepstone_suppression_set_rank UNIQUE (
        suppression_set_id,
        selection_rank
    ),
    CONSTRAINT chk_stepstone_suppression_set_item_values CHECK (
        baseline_card_count >= 1
        AND baseline_card_share > 0
        AND baseline_card_share <= 1
        AND first_position >= 1
        AND selection_rank >= 1
    )
);

CREATE TABLE IF NOT EXISTS stepstone_baseline_cycle_state (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL DEFAULT 'stepstone',
    search_profile_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    last_baseline_review_id BIGINT
        REFERENCES stepstone_company_discovery_cycle_reviews(id)
        ON DELETE SET NULL,
    active_suppression_set_id BIGINT
        REFERENCES stepstone_filter_suppression_sets(id)
        ON DELETE SET NULL,
    last_baseline_at TIMESTAMPTZ,
    next_baseline_due_at TIMESTAMPTZ,
    filtered_runs_since_baseline INTEGER NOT NULL DEFAULT 0,
    vocabulary_refresh_due BOOLEAN NOT NULL DEFAULT false,
    vocabulary_refresh_reason TEXT,
    novelty_degraded BOOLEAN NOT NULL DEFAULT false,
    transport_health_degraded BOOLEAN NOT NULL DEFAULT false,
    last_run_mode TEXT,
    last_run_at TIMESTAMPTZ,
    policy_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stepstone_baseline_cycle_scope UNIQUE (
        source_name,
        search_profile_name,
        search_term
    ),
    CONSTRAINT chk_stepstone_baseline_cycle_counts CHECK (
        filtered_runs_since_baseline >= 0
    ),
    CONSTRAINT chk_stepstone_baseline_cycle_mode CHECK (
        last_run_mode IS NULL OR last_run_mode IN ('baseline', 'filtered')
    ),
    CONSTRAINT chk_stepstone_baseline_vocabulary_reason CHECK (
        vocabulary_refresh_due OR vocabulary_refresh_reason IS NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_stepstone_baseline_cycle_due
    ON stepstone_baseline_cycle_state (
        source_name,
        next_baseline_due_at
    );

CREATE TABLE IF NOT EXISTS stepstone_origin_refresh_state (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL DEFAULT 'stepstone',
    search_profile_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    has_origin_connector BOOLEAN NOT NULL DEFAULT false,
    origin_connector_key TEXT,
    refresh_pending BOOLEAN NOT NULL DEFAULT false,
    refresh_cooldown_until TIMESTAMPTZ,
    last_triggered_at TIMESTAMPTZ,
    last_baseline_observed_at TIMESTAMPTZ,
    last_baseline_card_count INTEGER NOT NULL DEFAULT 0,
    last_baseline_card_share NUMERIC(8, 6) NOT NULL DEFAULT 0,
    total_trigger_count INTEGER NOT NULL DEFAULT 0,
    total_deduplicated_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stepstone_origin_refresh_scope UNIQUE (
        source_name,
        search_profile_name,
        search_term,
        company_key
    ),
    CONSTRAINT chk_stepstone_origin_refresh_connector CHECK (
        has_origin_connector OR origin_connector_key IS NULL
    ),
    CONSTRAINT chk_stepstone_origin_refresh_counts CHECK (
        last_baseline_card_count >= 0
        AND last_baseline_card_share BETWEEN 0 AND 1
        AND total_trigger_count >= 0
        AND total_deduplicated_count >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_stepstone_origin_refresh_due
    ON stepstone_origin_refresh_state (
        refresh_pending,
        refresh_cooldown_until
    );

CREATE TABLE IF NOT EXISTS stepstone_origin_refresh_signals (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL DEFAULT 'stepstone',
    search_profile_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    baseline_review_id BIGINT
        REFERENCES stepstone_company_discovery_cycle_reviews(id)
        ON DELETE SET NULL,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    card_count INTEGER NOT NULL,
    card_share NUMERIC(8, 6) NOT NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL,
    origin_connector_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_stepstone_origin_refresh_signal_values CHECK (
        card_count >= 1
        AND card_share > 0
        AND card_share <= 1
    ),
    CONSTRAINT chk_stepstone_origin_refresh_signal_action CHECK (
        action IN (
            'trigger_origin_refresh',
            'deduplicated_refresh_pending',
            'deduplicated_refresh_cooldown',
            'origin_discovery_signal'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_stepstone_origin_refresh_signals_company
    ON stepstone_origin_refresh_signals (
        company_key,
        created_at DESC
    );

CREATE TABLE IF NOT EXISTS stepstone_company_title_vocabulary (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL DEFAULT 'stepstone',
    search_profile_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    raw_title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    observation_count INTEGER NOT NULL DEFAULT 1,
    job_keys JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_mode TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stepstone_company_title_vocabulary UNIQUE (
        source_name,
        search_profile_name,
        search_term,
        company_key,
        normalized_title
    ),
    CONSTRAINT chk_stepstone_company_title_vocabulary_values CHECK (
        observation_count >= 1
        AND last_seen_at >= first_seen_at
        AND jsonb_typeof(job_keys) = 'array'
    ),
    CONSTRAINT chk_stepstone_company_title_vocabulary_mode CHECK (
        source_mode IN ('baseline', 'filtered')
    )
);

CREATE INDEX IF NOT EXISTS idx_stepstone_company_title_vocabulary_freshness
    ON stepstone_company_title_vocabulary (
        company_key,
        last_seen_at DESC
    );

-- Preserve the original readiness columns in their exact order and append the
-- decoupled control fields only at the end.
CREATE OR REPLACE VIEW gold_stepstone_dynamic_filter_policy_readiness AS
SELECT
    p.source_name,
    p.search_profile_name,
    p.search_term,
    p.status AS dynamic_policy_status,
    p.requested_filter_count,
    p.dominance_override_min_cards,
    p.dominance_override_min_share,
    p.reselection_cooldown_hours,
    p.validated_transport_name,
    p.transport_status,
    c.status AS capacity_policy_status,
    c.recommended_max_filter_count,
    c.supporting_completed_experiment_count,
    c.supporting_stable_trial_count,
    CASE
        WHEN p.status = 'approved'
         AND p.control_mode = 'decoupled_baseline_filter'
         AND p.suppression_source_mode = 'last_valid_baseline'
         AND p.transport_status = 'validated'
         AND c.status = 'approved'
         AND c.recommended_max_filter_count = p.requested_filter_count
        THEN 'ready_for_explicit_activation'
        ELSE 'blocked'
    END AS activation_readiness,
    p.policy_version AS dynamic_policy_version,
    c.policy_version AS capacity_policy_version,
    p.control_mode,
    p.suppression_source_mode,
    p.baseline_refresh_interval_hours,
    p.max_filtered_runs_between_baselines,
    p.vocabulary_staleness_hours,
    p.origin_refresh_cooldown_hours
FROM stepstone_dynamic_filter_policy p
LEFT JOIN stepstone_filter_capacity_policy c
  ON c.source_name = p.source_name
 AND c.search_profile_name = p.search_profile_name
 AND c.search_term = p.search_term
 AND c.transport_name = p.validated_transport_name;

CREATE OR REPLACE VIEW gold_stepstone_decoupled_cycle_state AS
SELECT
    s.source_name,
    s.search_profile_name,
    s.search_term,
    s.last_baseline_review_id,
    s.last_baseline_at,
    s.next_baseline_due_at,
    s.filtered_runs_since_baseline,
    s.vocabulary_refresh_due,
    s.vocabulary_refresh_reason,
    s.novelty_degraded,
    s.transport_health_degraded,
    s.last_run_mode,
    s.last_run_at,
    f.id AS active_suppression_set_id,
    f.selected_filter_count,
    f.transport_name,
    f.transport_status,
    f.status AS suppression_status,
    s.policy_version
FROM stepstone_baseline_cycle_state s
LEFT JOIN stepstone_filter_suppression_sets f
  ON f.id = s.active_suppression_set_id;

CREATE OR REPLACE VIEW gold_stepstone_origin_refresh_attention AS
SELECT
    source_name,
    search_profile_name,
    search_term,
    company_key,
    company_name,
    has_origin_connector,
    origin_connector_key,
    refresh_pending,
    refresh_cooldown_until,
    last_triggered_at,
    last_baseline_observed_at,
    last_baseline_card_count,
    last_baseline_card_share,
    total_trigger_count,
    total_deduplicated_count,
    CASE
        WHEN NOT has_origin_connector THEN 'origin_discovery_required'
        WHEN refresh_pending THEN 'refresh_pending'
        WHEN refresh_cooldown_until IS NOT NULL
         AND refresh_cooldown_until > now() THEN 'refresh_deduplicated_by_cooldown'
        ELSE 'refresh_eligible'
    END AS refresh_status
FROM stepstone_origin_refresh_state;
