-- STEPSTONE-DYNAMIC-FILTER-001
-- Persist n-1-derived filter selection, reselection cooldowns, dominance
-- overrides and filter-capacity evidence.
--
-- This migration does not activate StepStone requests or change the current
-- production planner. Query transport must first be permutation-invariant,
-- validated and operator-approved.
--
-- Boundaries: no source activation, no scheduler mutation, no provider call,
-- no candidate creation, no pagination and no detail-page request.

CREATE TABLE IF NOT EXISTS stepstone_company_reselection_state (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL DEFAULT 'stepstone',
    search_profile_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    reselection_cooldown_until TIMESTAMPTZ,
    last_selected_for_filter_at TIMESTAMPTZ,
    last_observed_at TIMESTAMPTZ,
    last_observed_card_count INTEGER NOT NULL DEFAULT 0,
    last_observed_card_share NUMERIC(8, 6) NOT NULL DEFAULT 0,
    total_selection_count INTEGER NOT NULL DEFAULT 0,
    total_dominance_override_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stepstone_company_reselection_scope UNIQUE (
        source_name,
        search_profile_name,
        search_term,
        company_key
    ),
    CONSTRAINT chk_stepstone_company_reselection_counts CHECK (
        last_observed_card_count >= 0
        AND total_selection_count >= 0
        AND total_dominance_override_count >= 0
    ),
    CONSTRAINT chk_stepstone_company_reselection_share CHECK (
        last_observed_card_share BETWEEN 0 AND 1
    )
);

CREATE INDEX IF NOT EXISTS idx_stepstone_company_reselection_due
    ON stepstone_company_reselection_state (
        source_name,
        search_profile_name,
        search_term,
        reselection_cooldown_until
    );

CREATE TABLE IF NOT EXISTS stepstone_dynamic_filter_selection_runs (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL DEFAULT 'stepstone',
    search_profile_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    predecessor_review_id BIGINT
        REFERENCES stepstone_company_discovery_cycle_reviews(id)
        ON DELETE SET NULL,
    predecessor_observed_at TIMESTAMPTZ NOT NULL,
    predecessor_observed_count INTEGER NOT NULL,
    predecessor_distinct_company_count INTEGER NOT NULL,
    requested_filter_count INTEGER NOT NULL,
    selected_filter_count INTEGER NOT NULL,
    transport_name TEXT,
    transport_status TEXT NOT NULL DEFAULT 'unvalidated',
    policy_version TEXT NOT NULL,
    selection_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_stepstone_dynamic_filter_counts CHECK (
        predecessor_observed_count >= 0
        AND predecessor_distinct_company_count >= 0
        AND requested_filter_count >= 1
        AND selected_filter_count >= 0
        AND selected_filter_count <= requested_filter_count
    ),
    CONSTRAINT chk_stepstone_dynamic_filter_transport_status CHECK (
        transport_status IN ('unvalidated', 'candidate', 'validated')
    ),
    CONSTRAINT chk_stepstone_dynamic_filter_metrics_object CHECK (
        jsonb_typeof(selection_metrics) = 'object'
    )
);

CREATE INDEX IF NOT EXISTS idx_stepstone_dynamic_filter_runs_scope
    ON stepstone_dynamic_filter_selection_runs (
        source_name,
        search_profile_name,
        search_term,
        predecessor_observed_at DESC
    );

CREATE TABLE IF NOT EXISTS stepstone_dynamic_filter_selection_items (
    id BIGSERIAL PRIMARY KEY,
    selection_run_id BIGINT NOT NULL
        REFERENCES stepstone_dynamic_filter_selection_runs(id)
        ON DELETE CASCADE,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    filter_alias TEXT NOT NULL,
    card_count INTEGER NOT NULL,
    card_share NUMERIC(8, 6) NOT NULL,
    first_position INTEGER NOT NULL,
    reselection_cooldown_until TIMESTAMPTZ,
    cooldown_active BOOLEAN NOT NULL DEFAULT false,
    dominance_override_applied BOOLEAN NOT NULL DEFAULT false,
    selected_for_next_run BOOLEAN NOT NULL DEFAULT false,
    selection_rank INTEGER,
    selection_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stepstone_dynamic_filter_item UNIQUE (
        selection_run_id,
        company_key
    ),
    CONSTRAINT chk_stepstone_dynamic_filter_item_values CHECK (
        card_count >= 0
        AND card_share BETWEEN 0 AND 1
        AND first_position >= 1
        AND (selection_rank IS NULL OR selection_rank >= 1)
    ),
    CONSTRAINT chk_stepstone_dynamic_filter_selection_rank CHECK (
        (selected_for_next_run AND selection_rank IS NOT NULL)
        OR (NOT selected_for_next_run AND selection_rank IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_stepstone_dynamic_filter_items_company
    ON stepstone_dynamic_filter_selection_items (
        company_key,
        created_at DESC
    );

CREATE TABLE IF NOT EXISTS stepstone_filter_capacity_experiments (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL DEFAULT 'stepstone',
    search_profile_name TEXT NOT NULL,
    search_term TEXT NOT NULL,
    selection_run_id BIGINT NOT NULL
        REFERENCES stepstone_dynamic_filter_selection_runs(id)
        ON DELETE RESTRICT,
    transport_name TEXT NOT NULL,
    transport_status TEXT NOT NULL,
    planned_maximum_filter_count INTEGER NOT NULL,
    request_budget INTEGER NOT NULL,
    cooldown_not_before TIMESTAMPTZ NOT NULL,
    approval_token_hash TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    policy_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT chk_stepstone_filter_capacity_transport CHECK (
        transport_status = 'validated'
    ),
    CONSTRAINT chk_stepstone_filter_capacity_values CHECK (
        planned_maximum_filter_count >= 1
        AND request_budget >= 1
    ),
    CONSTRAINT chk_stepstone_filter_capacity_status CHECK (
        status IN ('planned', 'blocked_by_cooldown', 'running', 'completed', 'aborted')
    )
);

CREATE TABLE IF NOT EXISTS stepstone_filter_capacity_trials (
    id BIGSERIAL PRIMARY KEY,
    experiment_id BIGINT NOT NULL
        REFERENCES stepstone_filter_capacity_experiments(id)
        ON DELETE CASCADE,
    filter_count INTEGER NOT NULL,
    permutation_name TEXT NOT NULL,
    company_keys JSONB NOT NULL,
    filter_aliases JSONB NOT NULL,
    intended_query TEXT NOT NULL,
    requested_url TEXT,
    final_url TEXT,
    page_type TEXT,
    page_fill_count INTEGER,
    distinct_company_count INTEGER,
    excluded_company_leakage_count INTEGER,
    new_company_count INTEGER,
    new_job_count INTEGER,
    job_overlap_count INTEGER,
    result_class TEXT NOT NULL DEFAULT 'planned',
    observed_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stepstone_filter_capacity_trial UNIQUE (
        experiment_id,
        filter_count,
        permutation_name
    ),
    CONSTRAINT chk_stepstone_filter_capacity_trial_arrays CHECK (
        jsonb_typeof(company_keys) = 'array'
        AND jsonb_typeof(filter_aliases) = 'array'
    ),
    CONSTRAINT chk_stepstone_filter_capacity_trial_counts CHECK (
        filter_count >= 1
        AND (page_fill_count IS NULL OR page_fill_count BETWEEN 0 AND 25)
        AND (distinct_company_count IS NULL OR distinct_company_count >= 0)
        AND (
            excluded_company_leakage_count IS NULL
            OR excluded_company_leakage_count >= 0
        )
        AND (new_company_count IS NULL OR new_company_count >= 0)
        AND (new_job_count IS NULL OR new_job_count >= 0)
        AND (job_overlap_count IS NULL OR job_overlap_count >= 0)
    ),
    CONSTRAINT chk_stepstone_filter_capacity_result_class CHECK (
        result_class IN (
            'planned',
            'full_refill_permutation_stable',
            'partial_refill_permutation_stable',
            'same_filter_set_not_permutation_invariant',
            'excluded_company_leakage',
            'explicit_zero_results',
            'technical_indeterminate'
        )
    ),
    CONSTRAINT chk_stepstone_filter_capacity_evidence_object CHECK (
        jsonb_typeof(evidence) = 'object'
    )
);

CREATE INDEX IF NOT EXISTS idx_stepstone_filter_capacity_trials_evidence
    ON stepstone_filter_capacity_trials (
        experiment_id,
        filter_count,
        permutation_name
    );

CREATE OR REPLACE VIEW gold_stepstone_company_discovery_longitudinal AS
SELECT
    r.source_name,
    r.search_profile_name,
    r.search_term,
    i.company_key,
    max(i.company_name) AS company_name,
    count(*) AS observed_run_count,
    sum(i.card_count) AS total_observed_cards,
    avg(i.card_share) AS average_page_share,
    max(i.card_share) AS maximum_page_share,
    count(*) FILTER (WHERE i.selected_for_next_run) AS selected_filter_count,
    count(*) FILTER (WHERE i.dominance_override_applied) AS dominance_override_count,
    max(r.predecessor_observed_at) AS last_observed_at,
    max(i.reselection_cooldown_until) AS latest_reselection_cooldown_until
FROM stepstone_dynamic_filter_selection_runs r
JOIN stepstone_dynamic_filter_selection_items i
  ON i.selection_run_id = r.id
GROUP BY
    r.source_name,
    r.search_profile_name,
    r.search_term,
    i.company_key;

CREATE OR REPLACE VIEW gold_stepstone_filter_capacity_evidence AS
SELECT
    e.source_name,
    e.search_profile_name,
    e.search_term,
    e.transport_name,
    t.filter_count,
    count(*) FILTER (
        WHERE t.result_class = 'full_refill_permutation_stable'
    ) AS full_refill_trial_count,
    count(*) FILTER (
        WHERE t.result_class = 'partial_refill_permutation_stable'
    ) AS partial_refill_trial_count,
    count(*) FILTER (
        WHERE t.result_class = 'same_filter_set_not_permutation_invariant'
    ) AS non_invariant_trial_count,
    count(*) FILTER (
        WHERE t.result_class = 'excluded_company_leakage'
    ) AS leakage_trial_count,
    avg(t.page_fill_count) FILTER (
        WHERE t.page_fill_count IS NOT NULL
    ) AS average_page_fill_count,
    avg(t.new_company_count) FILTER (
        WHERE t.new_company_count IS NOT NULL
    ) AS average_new_company_count,
    max(t.observed_at) AS last_observed_at
FROM stepstone_filter_capacity_experiments e
JOIN stepstone_filter_capacity_trials t
  ON t.experiment_id = e.id
GROUP BY
    e.source_name,
    e.search_profile_name,
    e.search_term,
    e.transport_name,
    t.filter_count;
