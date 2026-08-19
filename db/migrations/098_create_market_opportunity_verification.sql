-- Product V1 observed-opportunity bridge.
--
-- Market evidence remains observational and cannot become ranking/application truth
-- merely by passing this bridge. The bridge records exact-vacancy verification
-- outcomes and projects the current state for Product V1/read-only UX.

CREATE TABLE IF NOT EXISTS market_opportunity_verification_observations (
    id BIGSERIAL PRIMARY KEY,
    market_evidence_id BIGINT NOT NULL
        REFERENCES market_evidence(id) ON DELETE CASCADE,
    candidate_id BIGINT
        REFERENCES employer_origin_source_candidates(id) ON DELETE SET NULL,
    outcome TEXT NOT NULL CHECK (outcome IN (
        'verified_active',
        'verified_closed',
        'unverifiable',
        'employer_candidate_missing',
        'risk_gate_blocked',
        'origin_source_required',
        'detail_candidate_required'
    )),
    resolved_url TEXT,
    evidence_reason TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    observed_by TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_opportunity_verification_evidence
ON market_opportunity_verification_observations (
    market_evidence_id,
    observed_at DESC,
    id DESC
);

CREATE INDEX IF NOT EXISTS idx_market_opportunity_verification_candidate
ON market_opportunity_verification_observations (
    candidate_id,
    observed_at DESC,
    id DESC
);

CREATE OR REPLACE VIEW gold_market_opportunity_status AS
SELECT
    me.id AS opportunity_id,
    me.evidence_source,
    me.source_name AS observation_channel,
    me.normalized_company_key,
    me.company_name,
    me.title,
    me.evidence_url,
    me.search_profile_name,
    me.search_term,
    me.source_seen_at,
    me.observed_at,
    me.evidence AS market_evidence,
    candidate.id AS candidate_id,
    candidate.status AS candidate_status,
    candidate.risk_level AS candidate_risk_level,
    candidate.candidate_url AS employer_origin_url,
    latest.id AS verification_observation_id,
    latest.outcome AS verification_outcome,
    latest.resolved_url AS verified_vacancy_url,
    latest.evidence_reason AS verification_reason,
    latest.evidence AS verification_evidence,
    latest.observed_at AS verification_observed_at,
    CASE
        WHEN latest.outcome = 'verified_active' THEN 'vacancy_verified_active'
        WHEN latest.outcome = 'verified_closed' THEN 'vacancy_verified_closed'
        WHEN latest.outcome = 'risk_gate_blocked' THEN 'risk_review'
        WHEN latest.outcome = 'origin_source_required' THEN 'origin_source_required'
        WHEN latest.outcome = 'employer_candidate_missing' THEN 'employer_candidate_missing'
        WHEN latest.outcome IN ('detail_candidate_required', 'unverifiable')
            THEN 'vacancy_verification_pending'
        WHEN candidate.id IS NULL THEN 'employer_candidate_missing'
        WHEN candidate.risk_level IN ('high', 'blocked') THEN 'risk_review'
        WHEN candidate.candidate_url IS NULL OR btrim(candidate.candidate_url) = ''
            THEN 'origin_source_required'
        ELSE 'vacancy_verification_pending'
    END AS opportunity_stage,
    FALSE AS ranking_authority,
    FALSE AS application_authority
FROM market_evidence me
LEFT JOIN LATERAL (
    SELECT c.id, c.status, c.risk_level, c.candidate_url
    FROM employer_origin_source_candidates c
    WHERE
        c.company_key = me.normalized_company_key
        OR starts_with(me.normalized_company_key, c.company_key || '_')
        OR starts_with(c.company_key, me.normalized_company_key || '_')
    ORDER BY
        CASE WHEN c.company_key = me.normalized_company_key THEN 0 ELSE 1 END,
        c.updated_at DESC,
        c.id DESC
    LIMIT 1
) candidate ON TRUE
LEFT JOIN LATERAL (
    SELECT
        v.id,
        v.outcome,
        v.resolved_url,
        v.evidence_reason,
        v.evidence,
        v.observed_at
    FROM market_opportunity_verification_observations v
    WHERE v.market_evidence_id = me.id
    ORDER BY v.observed_at DESC, v.id DESC
    LIMIT 1
) latest ON TRUE
WHERE me.evidence_kind = 'external_market_observation';

COMMENT ON VIEW gold_market_opportunity_status IS
'Observed market opportunities and exact-vacancy verification state. This view has no ranking or application authority; canonical Silver/Product V1 admission remains separate.';
