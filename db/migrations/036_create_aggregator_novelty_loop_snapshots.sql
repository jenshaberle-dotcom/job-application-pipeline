-- S6B Aggregator Novelty Loop Foundation
-- Tracks whether bounded aggregator exploration is still producing genuinely
-- new company and vocabulary evidence across cycles. This is review/learning
-- state only: no pagination, no source activation, no search-profile mutation,
-- no Bronze writes and no scheduler changes.
--
-- Semantics:
-- - unregistered_company_count: observed companies not yet modeled as
--   employer-origin candidates.
-- - newly_observed_company_count: companies not present in the previous
--   persisted novelty snapshot for the same source/search scope.
-- These are intentionally separate; an unregistered company can still be a
-- repeated observation and therefore should not be counted as cycle novelty.

CREATE TABLE IF NOT EXISTS aggregator_novelty_snapshots (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    search_profile_name TEXT,
    search_term TEXT,
    cycle_scope TEXT NOT NULL DEFAULT 'bounded_aggregator_market_evidence',
    previous_snapshot_id BIGINT REFERENCES aggregator_novelty_snapshots(id) ON DELETE SET NULL,
    observed_since TIMESTAMPTZ,
    observed_until TIMESTAMPTZ,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    distinct_company_count INTEGER NOT NULL DEFAULT 0,
    unregistered_company_count INTEGER NOT NULL DEFAULT 0,
    known_candidate_company_count INTEGER NOT NULL DEFAULT 0,
    newly_observed_company_count INTEGER NOT NULL DEFAULT 0,
    repeated_observed_company_count INTEGER NOT NULL DEFAULT 0,
    reassessment_company_count INTEGER NOT NULL DEFAULT 0,
    new_vocabulary_term_count INTEGER NOT NULL DEFAULT 0,
    known_vocabulary_term_count INTEGER NOT NULL DEFAULT 0,
    newly_observed_term_count INTEGER NOT NULL DEFAULT 0,
    repeated_observed_term_count INTEGER NOT NULL DEFAULT 0,
    novelty_score NUMERIC(5,2) NOT NULL DEFAULT 0,
    saturation_level TEXT NOT NULL DEFAULT 'unknown',
    recommended_action TEXT NOT NULL DEFAULT 'manual_review',
    reason TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by TEXT NOT NULL DEFAULT 'agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_aggregator_novelty_snapshot_counts CHECK (
        evidence_count >= 0
        AND distinct_company_count >= 0
        AND unregistered_company_count >= 0
        AND known_candidate_company_count >= 0
        AND newly_observed_company_count >= 0
        AND repeated_observed_company_count >= 0
        AND reassessment_company_count >= 0
        AND new_vocabulary_term_count >= 0
        AND known_vocabulary_term_count >= 0
        AND newly_observed_term_count >= 0
        AND repeated_observed_term_count >= 0
        AND distinct_company_count = unregistered_company_count + known_candidate_company_count
        AND distinct_company_count = newly_observed_company_count + repeated_observed_company_count
    ),
    CONSTRAINT chk_aggregator_novelty_score CHECK (novelty_score >= 0 AND novelty_score <= 1),
    CONSTRAINT chk_aggregator_novelty_saturation CHECK (
        saturation_level IN ('unknown', 'baseline', 'fresh', 'mixed', 'saturating', 'saturated')
    ),
    CONSTRAINT chk_aggregator_novelty_action CHECK (
        recommended_action IN (
            'manual_review',
            'persist_baseline_then_rerun',
            'continue_bounded_exploration',
            'review_newly_observed_companies',
            'review_unregistered_company_backlog',
            'rerun_gate_reassessment_for_known_candidates',
            'try_reviewed_trial_terms',
            'pause_or_retire_current_query'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_aggregator_novelty_snapshots_source_created
    ON aggregator_novelty_snapshots (source_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_aggregator_novelty_snapshots_scope_action
    ON aggregator_novelty_snapshots (cycle_scope, recommended_action, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_aggregator_novelty_snapshots_scope_previous
    ON aggregator_novelty_snapshots (source_name, search_profile_name, search_term, created_at DESC);

CREATE TABLE IF NOT EXISTS aggregator_novelty_items (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL
        REFERENCES aggregator_novelty_snapshots(id)
        ON DELETE CASCADE,
    item_type TEXT NOT NULL,
    novelty_state TEXT NOT NULL,
    source_name TEXT NOT NULL,
    company_key TEXT,
    company_name TEXT,
    title TEXT,
    search_profile_name TEXT,
    search_term TEXT,
    observed_term TEXT,
    known_candidate_id BIGINT REFERENCES employer_origin_source_candidates(id) ON DELETE SET NULL,
    known_candidate_status TEXT,
    evidence_url TEXT,
    observed_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_aggregator_novelty_item_type CHECK (
        item_type IN ('company', 'term', 'candidate_reassessment')
    ),
    CONSTRAINT chk_aggregator_novelty_state CHECK (
        novelty_state IN (
            'unregistered_company',
            'known_candidate_company',
            'new_vocabulary_term',
            'known_vocabulary_term',
            'known_candidate_reassessment'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_aggregator_novelty_items_snapshot
    ON aggregator_novelty_items (snapshot_id);

CREATE INDEX IF NOT EXISTS idx_aggregator_novelty_items_state
    ON aggregator_novelty_items (novelty_state, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_aggregator_novelty_items_company
    ON aggregator_novelty_items (company_key, created_at DESC);
