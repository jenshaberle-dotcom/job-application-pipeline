-- A1b action-run observability for Control Center initiated actions.
--
-- Purpose:
--   Persist every GUI-triggered Search Intelligence action even when the
--   underlying agent fails before it can write a gate review. This closes the
--   observability gap between "button clicked", command execution and persisted
--   gate state.
--
-- Boundary:
-- - This table records action execution metadata and diagnostic tails only.
-- - It does not activate sources, register connectors, write Bronze records or
--   mutate scheduler configuration.
-- - It is intentionally separate from gate reviews: an action run is an
--   operational fact; a gate review is a domain decision.

CREATE TABLE IF NOT EXISTS search_intelligence_action_runs (
    id BIGSERIAL PRIMARY KEY,
    action_type TEXT NOT NULL,
    company_key TEXT NOT NULL,
    candidate_id BIGINT,
    reviewed_by TEXT,
    triggered_from TEXT NOT NULL DEFAULT 'control_center',
    command TEXT NOT NULL,
    status TEXT NOT NULL,
    exit_code INTEGER,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    stdout_tail TEXT,
    stderr_tail TEXT,
    error_summary TEXT,
    gate_review_created BOOLEAN,
    gate_review_gate_name TEXT,
    gate_review_status TEXT,
    gate_review_decision TEXT,
    gate_review_created_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_search_intelligence_action_runs_status
        CHECK (status IN ('running', 'success', 'failed', 'blocked')),
    CONSTRAINT chk_search_intelligence_action_runs_action_type
        CHECK (action_type IN ('rerun_evidence_repair', 'approve_connector_build', 'approve_connector_registration')),
    CONSTRAINT chk_search_intelligence_action_runs_finished_at
        CHECK ((status = 'running' AND finished_at IS NULL) OR (status <> 'running' AND finished_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_search_intelligence_action_runs_candidate_started
    ON search_intelligence_action_runs (candidate_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_intelligence_action_runs_company_started
    ON search_intelligence_action_runs (company_key, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_intelligence_action_runs_status_started
    ON search_intelligence_action_runs (status, started_at DESC);

COMMENT ON TABLE search_intelligence_action_runs IS
    'Operational audit trail for Search Intelligence Control Center actions. Persists failed runs even when no gate review is written.';

COMMENT ON COLUMN search_intelligence_action_runs.gate_review_created IS
    'True when the action produced a newer gate review for the candidate/action target after the run started.';
