-- STEPSTONE-DYNAMIC-FILTER-002
-- Version and gate the dynamic n-1 selection policy and the empirically
-- supported maximum filter length.
--
-- No default policy row is inserted. Absence of an approved row means that the
-- dynamic policy remains inactive. Values must be evidence-backed and operator
-- approved after query-transport and capacity validation.

CREATE TABLE IF NOT EXISTS stepstone_dynamic_filter_policy (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL DEFAULT 'stepstone',
    search_profile_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'operator_decision_required',
    requested_filter_count INTEGER,
    dominance_override_min_cards INTEGER,
    dominance_override_min_share NUMERIC(8, 6),
    reselection_cooldown_hours INTEGER,
    validated_transport_name TEXT,
    transport_status TEXT NOT NULL DEFAULT 'unvalidated',
    policy_version TEXT NOT NULL,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stepstone_dynamic_filter_policy_scope UNIQUE (
        source_name,
        search_profile_name,
        search_term
    ),
    CONSTRAINT chk_stepstone_dynamic_filter_policy_status CHECK (
        status IN ('operator_decision_required', 'candidate', 'approved', 'superseded')
    ),
    CONSTRAINT chk_stepstone_dynamic_filter_policy_transport CHECK (
        transport_status IN ('unvalidated', 'candidate', 'validated')
    ),
    CONSTRAINT chk_stepstone_dynamic_filter_policy_values CHECK (
        (requested_filter_count IS NULL OR requested_filter_count >= 1)
        AND (
            dominance_override_min_cards IS NULL
            OR dominance_override_min_cards >= 1
        )
        AND (
            dominance_override_min_share IS NULL
            OR dominance_override_min_share > 0
               AND dominance_override_min_share <= 1
        )
        AND (
            reselection_cooldown_hours IS NULL
            OR reselection_cooldown_hours >= 0
        )
    ),
    CONSTRAINT chk_stepstone_dynamic_filter_policy_approval CHECK (
        status <> 'approved'
        OR (
            requested_filter_count IS NOT NULL
            AND dominance_override_min_cards IS NOT NULL
            AND dominance_override_min_share IS NOT NULL
            AND reselection_cooldown_hours IS NOT NULL
            AND validated_transport_name IS NOT NULL
            AND transport_status = 'validated'
            AND approved_by IS NOT NULL
            AND approved_at IS NOT NULL
        )
    )
);

CREATE TABLE IF NOT EXISTS stepstone_filter_capacity_policy (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL DEFAULT 'stepstone',
    search_profile_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    transport_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'diagnostic_only',
    recommended_max_filter_count INTEGER,
    supporting_completed_experiment_count INTEGER NOT NULL DEFAULT 0,
    supporting_stable_trial_count INTEGER NOT NULL DEFAULT 0,
    last_supporting_experiment_id BIGINT
        REFERENCES stepstone_filter_capacity_experiments(id)
        ON DELETE SET NULL,
    policy_version TEXT NOT NULL,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stepstone_filter_capacity_policy_scope UNIQUE (
        source_name,
        search_profile_name,
        search_term,
        transport_name
    ),
    CONSTRAINT chk_stepstone_filter_capacity_policy_status CHECK (
        status IN ('diagnostic_only', 'candidate', 'approved', 'superseded')
    ),
    CONSTRAINT chk_stepstone_filter_capacity_policy_counts CHECK (
        (recommended_max_filter_count IS NULL OR recommended_max_filter_count >= 1)
        AND supporting_completed_experiment_count >= 0
        AND supporting_stable_trial_count >= 0
    ),
    CONSTRAINT chk_stepstone_filter_capacity_policy_approval CHECK (
        status <> 'approved'
        OR (
            recommended_max_filter_count IS NOT NULL
            AND supporting_completed_experiment_count >= 1
            AND supporting_stable_trial_count >= 1
            AND last_supporting_experiment_id IS NOT NULL
            AND approved_by IS NOT NULL
            AND approved_at IS NOT NULL
        )
    )
);

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
         AND p.transport_status = 'validated'
         AND c.status = 'approved'
         AND c.recommended_max_filter_count = p.requested_filter_count
        THEN 'ready_for_explicit_activation'
        ELSE 'blocked'
    END AS activation_readiness,
    p.policy_version AS dynamic_policy_version,
    c.policy_version AS capacity_policy_version
FROM stepstone_dynamic_filter_policy p
LEFT JOIN stepstone_filter_capacity_policy c
  ON c.source_name = p.source_name
 AND c.search_profile_name = p.search_profile_name
 AND c.search_term = p.search_term
 AND c.transport_name = p.validated_transport_name;
