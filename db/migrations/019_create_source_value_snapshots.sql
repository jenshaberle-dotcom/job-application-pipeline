CREATE TABLE source_value_snapshots (
    id BIGSERIAL PRIMARY KEY,

    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    snapshot_reason TEXT NOT NULL DEFAULT 'manual',

    source_name TEXT NOT NULL,
    source_family TEXT NOT NULL,
    source_target TEXT,
    source_type TEXT,

    evaluation_window_started_at TIMESTAMPTZ,
    evaluation_window_finished_at TIMESTAMPTZ,

    ingestion_runs INTEGER NOT NULL DEFAULT 0,
    successful_runs INTEGER NOT NULL DEFAULT 0,
    failed_runs INTEGER NOT NULL DEFAULT 0,

    fetched_jobs_before_filter INTEGER,
    matched_jobs_after_filter INTEGER NOT NULL DEFAULT 0,
    inserted_jobs INTEGER NOT NULL DEFAULT 0,
    duplicate_jobs INTEGER NOT NULL DEFAULT 0,

    raw_jobs INTEGER NOT NULL DEFAULT 0,
    silver_jobs INTEGER NOT NULL DEFAULT 0,
    distinct_companies INTEGER NOT NULL DEFAULT 0,
    distinct_candidate_keys INTEGER NOT NULL DEFAULT 0,

    rows_in_duplicate_candidate_groups INTEGER NOT NULL DEFAULT 0,
    rows_in_cross_source_candidate_groups INTEGER NOT NULL DEFAULT 0,
    cross_source_candidate_keys INTEGER NOT NULL DEFAULT 0,

    title_completeness_pct NUMERIC(5, 2),
    company_completeness_pct NUMERIC(5, 2),
    location_completeness_pct NUMERIC(5, 2),
    publication_date_completeness_pct NUMERIC(5, 2),

    matched_rate_pct NUMERIC(5, 2),
    duplicate_rate_pct NUMERIC(5, 2),
    failure_rate_pct NUMERIC(5, 2),

    source_value_score NUMERIC(6, 2),
    lifecycle_state TEXT,
    recommendation TEXT,
    notes TEXT,

    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_source_value_snapshots_source_name_snapshot_at
    ON source_value_snapshots (source_name, snapshot_at DESC);

CREATE INDEX idx_source_value_snapshots_source_family_snapshot_at
    ON source_value_snapshots (source_family, snapshot_at DESC);

CREATE INDEX idx_source_value_snapshots_source_target
    ON source_value_snapshots (source_target);

CREATE INDEX idx_source_value_snapshots_lifecycle_state
    ON source_value_snapshots (lifecycle_state);

COMMENT ON TABLE source_value_snapshots IS
    'Historical snapshots of source-value metrics for source families, source targets and operational source names.';

COMMENT ON COLUMN source_value_snapshots.source_name IS
    'Current operational source identifier, for example greenhouse:stripe or personio:eraneos.';

COMMENT ON COLUMN source_value_snapshots.source_family IS
    'Source family according to ADR-028, for example greenhouse, personio, stepstone or bundesagentur_fuer_arbeit.';

COMMENT ON COLUMN source_value_snapshots.source_target IS
    'Concrete source target according to ADR-028, for example stripe, eraneos or schluetersche-mediengruppe.';

COMMENT ON COLUMN source_value_snapshots.source_type IS
    'Strategic source type, for example official_api, ats_company_board, commercial_aggregator or discovery_source.';

COMMENT ON COLUMN source_value_snapshots.fetched_jobs_before_filter IS
    'Nullable future metric for source records fetched before local search-intent filtering.';

COMMENT ON COLUMN source_value_snapshots.matched_jobs_after_filter IS
    'Jobs counted after source-side or local search-intent filtering, based on current ingestion_run semantics.';

COMMENT ON COLUMN source_value_snapshots.metrics IS
    'Additional metric payload for experimental or future source-value dimensions without immediate schema changes.';
