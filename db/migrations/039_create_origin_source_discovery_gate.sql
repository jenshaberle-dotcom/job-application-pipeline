-- S7D Origin Source Discovery Gate Foundation
--
-- Purpose:
--   Make origin-source URL discovery an explicit, DB-backed gate before
--   connector artifact generation. The gate records which origin URL was
--   selected, why it was selected, which alternatives were seen and why unsafe
--   or ambiguous URLs were rejected.
--
-- Boundary:
--   - no web browsing or probing inside this migration
--   - no connector registration
--   - no source activation
--   - no Bronze writes
--   - no scheduler changes
--   - no CSV/Excel/export artifact as pipeline input

CREATE TABLE IF NOT EXISTS employer_origin_source_discovery_reviews (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT NOT NULL
        REFERENCES employer_origin_source_candidates (id)
        ON DELETE CASCADE,
    discovery_status TEXT NOT NULL,
    decision TEXT NOT NULL,
    selected_origin_url TEXT,
    selected_domain TEXT,
    selected_source_type TEXT,
    confidence_score NUMERIC(5,2) NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL DEFAULT 'unknown',
    blocker_code TEXT,
    reason TEXT NOT NULL,
    alternatives JSONB NOT NULL DEFAULT '[]'::jsonb,
    rejected_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by TEXT NOT NULL DEFAULT 'agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (candidate_id),
    CONSTRAINT chk_employer_origin_source_discovery_status CHECK (
        discovery_status IN (
            'selected',
            'manual_review_required',
            'blocked_unsafe_url',
            'not_found',
            'not_applicable'
        )
    ),
    CONSTRAINT chk_employer_origin_source_discovery_decision CHECK (
        decision IN (
            'continue_to_connector_feasibility',
            'manual_review_required',
            'abort_documented',
            'monitor_existing_source'
        )
    ),
    CONSTRAINT chk_employer_origin_source_discovery_risk CHECK (
        risk_level IN ('unknown', 'low', 'medium', 'high', 'blocked')
    ),
    CONSTRAINT chk_employer_origin_source_discovery_confidence CHECK (
        confidence_score >= 0 AND confidence_score <= 1
    ),
    CONSTRAINT chk_employer_origin_source_discovery_selection CHECK (
        discovery_status <> 'selected'
        OR (selected_origin_url IS NOT NULL AND selected_domain IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_employer_origin_source_discovery_status
    ON employer_origin_source_discovery_reviews (discovery_status, decision, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_employer_origin_source_discovery_candidate
    ON employer_origin_source_discovery_reviews (candidate_id);

CREATE OR REPLACE VIEW gold_origin_source_discovery_status AS
SELECT
    c.id AS candidate_id,
    c.company_key,
    c.company_name,
    c.status AS candidate_status,
    c.candidate_url,
    c.source_name_candidate,
    c.source_type_candidate,
    r.discovery_status,
    r.decision,
    r.selected_origin_url,
    r.selected_domain,
    r.selected_source_type,
    r.confidence_score,
    r.risk_level,
    r.blocker_code,
    r.reason,
    r.updated_at AS reviewed_at
FROM employer_origin_source_candidates c
LEFT JOIN employer_origin_source_discovery_reviews r
    ON r.candidate_id = c.id;
