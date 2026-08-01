-- PRODUCT-V1-MONOLITH-001
-- Integrated data contracts for:
--   1. persistent StepStone company-discovery waves,
--   2. origin-gated Top-5 job serving,
--   3. source-grounded CV/application-letter assistance,
--   4. Control Center serving through stable read models.
--
-- Open product decisions remain explicit gates. This migration does not choose
-- ranking weights, freshness limits, hard-filter semantics or operator actions.
-- It does not run sources, call a provider, apply to a job or mutate a scheduler.

ALTER TABLE search_term_cycle_state
ADD COLUMN IF NOT EXISTS current_exclusion_wave_index INTEGER NOT NULL DEFAULT 0;

ALTER TABLE search_term_cycle_state
ADD COLUMN IF NOT EXISTS last_wave_action TEXT;

ALTER TABLE search_term_cycle_state
ADD COLUMN IF NOT EXISTS last_wave_completed_at TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_search_term_cycle_wave_index'
    ) THEN
        ALTER TABLE search_term_cycle_state
        ADD CONSTRAINT chk_search_term_cycle_wave_index
        CHECK (current_exclusion_wave_index >= 0);
    END IF;
END $$;

ALTER TABLE stepstone_company_discovery_cycle_reviews
DROP CONSTRAINT IF EXISTS chk_stepstone_company_cycle_action;

ALTER TABLE stepstone_company_discovery_cycle_reviews
ADD CONSTRAINT chk_stepstone_company_cycle_action CHECK (
    action IN (
        'run_baseline_only',
        'run_baseline_learning',
        'run_fetch_time_company_not_probe',
        'skip_empty_exclusion_wave'
    )
);

CREATE TABLE IF NOT EXISTS product_v1_ranking_policy (
    policy_key TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'operator_decision_required',
    top_job_limit INTEGER,
    minimum_quality_score NUMERIC(6, 2),
    ranking_weights JSONB NOT NULL DEFAULT '{}'::jsonb,
    explanation_mode TEXT,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_product_v1_ranking_policy_key CHECK (policy_key = 'default'),
    CONSTRAINT chk_product_v1_ranking_policy_status CHECK (
        status IN ('operator_decision_required', 'approved', 'superseded')
    ),
    CONSTRAINT chk_product_v1_ranking_policy_limit CHECK (
        top_job_limit IS NULL OR top_job_limit BETWEEN 1 AND 25
    ),
    CONSTRAINT chk_product_v1_ranking_policy_threshold CHECK (
        minimum_quality_score IS NULL
        OR minimum_quality_score BETWEEN 0 AND 100
    )
);

INSERT INTO product_v1_ranking_policy (
    policy_key,
    status,
    top_job_limit,
    minimum_quality_score,
    ranking_weights,
    explanation_mode
)
VALUES (
    'default',
    'operator_decision_required',
    NULL,
    NULL,
    '{}'::jsonb,
    NULL
)
ON CONFLICT (policy_key) DO NOTHING;

CREATE TABLE IF NOT EXISTS job_product_assessments (
    silver_job_id BIGINT PRIMARY KEY REFERENCES silver_jobs(id) ON DELETE CASCADE,
    origin_validation_status TEXT NOT NULL DEFAULT 'pending',
    activity_status TEXT NOT NULL DEFAULT 'unknown',
    hard_filter_status TEXT NOT NULL DEFAULT 'unknown',
    profile_direction_score NUMERIC(6, 2),
    data_focus_score NUMERIC(6, 2),
    reliability_focus_score NUMERIC(6, 2),
    evidence_quality_score NUMERIC(6, 2),
    overall_quality_score NUMERIC(6, 2),
    work_model TEXT NOT NULL DEFAULT 'unknown',
    commute_minutes INTEGER,
    public_transport_quality TEXT NOT NULL DEFAULT 'unknown',
    ranking_factors JSONB NOT NULL DEFAULT '{}'::jsonb,
    explanations JSONB NOT NULL DEFAULT '[]'::jsonb,
    uncertainties JSONB NOT NULL DEFAULT '[]'::jsonb,
    policy_key TEXT REFERENCES product_v1_ranking_policy(policy_key),
    policy_version TEXT,
    assessed_by TEXT NOT NULL DEFAULT 'deterministic_product_v1',
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_job_product_origin_validation CHECK (
        origin_validation_status IN ('validated', 'rejected', 'pending')
    ),
    CONSTRAINT chk_job_product_activity CHECK (
        activity_status IN ('active', 'inactive', 'unknown')
    ),
    CONSTRAINT chk_job_product_hard_filter CHECK (
        hard_filter_status IN ('passed', 'failed', 'unknown')
    ),
    CONSTRAINT chk_job_product_work_model CHECK (
        work_model IN ('hybrid', 'onsite', 'remote', 'unknown')
    ),
    CONSTRAINT chk_job_product_public_transport CHECK (
        public_transport_quality IN ('good', 'acceptable', 'poor', 'unknown')
    ),
    CONSTRAINT chk_job_product_commute CHECK (
        commute_minutes IS NULL OR commute_minutes >= 0
    ),
    CONSTRAINT chk_job_product_scores CHECK (
        (profile_direction_score IS NULL OR profile_direction_score BETWEEN 0 AND 100)
        AND (data_focus_score IS NULL OR data_focus_score BETWEEN 0 AND 100)
        AND (reliability_focus_score IS NULL OR reliability_focus_score BETWEEN 0 AND 100)
        AND (evidence_quality_score IS NULL OR evidence_quality_score BETWEEN 0 AND 100)
        AND (overall_quality_score IS NULL OR overall_quality_score BETWEEN 0 AND 100)
    )
);

CREATE INDEX IF NOT EXISTS idx_job_product_assessments_rankable
ON job_product_assessments (
    origin_validation_status,
    activity_status,
    hard_filter_status,
    overall_quality_score DESC
);

CREATE TABLE IF NOT EXISTS application_source_documents (
    id BIGSERIAL PRIMARY KEY,
    document_type TEXT NOT NULL,
    source_label TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'registered',
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_application_source_document_type CHECK (
        document_type IN ('base_cv', 'base_application_letter', 'approved_fact_source')
    ),
    CONSTRAINT chk_application_source_document_status CHECK (
        status IN ('registered', 'approved', 'superseded', 'rejected')
    ),
    CONSTRAINT uq_application_source_document_hash UNIQUE (
        document_type,
        content_sha256
    )
);

CREATE TABLE IF NOT EXISTS application_draft_requests (
    id BIGSERIAL PRIMARY KEY,
    silver_job_id BIGINT NOT NULL REFERENCES silver_jobs(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'blocked_missing_sources',
    source_manifest JSONB NOT NULL DEFAULT '{}'::jsonb,
    draft_payload JSONB,
    review_notes TEXT,
    requested_by TEXT NOT NULL DEFAULT 'jens',
    reviewed_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_application_draft_request_status CHECK (
        status IN (
            'blocked_missing_sources',
            'blocked_job_not_eligible',
            'ready_for_generation',
            'drafted_for_review',
            'approved_by_operator',
            'rejected_by_operator'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_application_draft_requests_job
ON application_draft_requests (silver_job_id, created_at DESC);

CREATE OR REPLACE VIEW gold_product_v1_job_readiness AS
SELECT
    sj.id AS silver_job_id,
    sj.title,
    sj.company_name,
    sj.city,
    sj.country,
    sj.publication_date,
    sj.source_name,
    sj.source_url,
    sj.canonical_source_type,
    a.origin_validation_status,
    a.activity_status,
    a.hard_filter_status,
    a.profile_direction_score,
    a.data_focus_score,
    a.reliability_focus_score,
    a.evidence_quality_score,
    a.overall_quality_score,
    a.work_model,
    a.commute_minutes,
    a.public_transport_quality,
    a.explanations,
    a.uncertainties,
    a.policy_key,
    a.policy_version,
    CASE
        WHEN a.silver_job_id IS NULL THEN 'assessment_required'
        WHEN a.origin_validation_status = 'rejected' THEN 'blocked_origin'
        WHEN a.origin_validation_status = 'pending' THEN 'origin_validation_required'
        WHEN a.activity_status = 'inactive' THEN 'blocked_inactive'
        WHEN a.activity_status = 'unknown' THEN 'activity_evidence_required'
        WHEN a.hard_filter_status = 'failed' THEN 'blocked_hard_filter'
        WHEN a.hard_filter_status = 'unknown' THEN 'hard_filter_decision_required'
        WHEN a.overall_quality_score IS NULL THEN 'ranking_policy_required'
        ELSE 'rankable'
    END AS product_readiness_status
FROM silver_jobs sj
LEFT JOIN job_product_assessments a
  ON a.silver_job_id = sj.id;

CREATE OR REPLACE VIEW gold_product_v1_top_jobs AS
WITH approved_policy AS (
    SELECT *
    FROM product_v1_ranking_policy
    WHERE policy_key = 'default'
      AND status = 'approved'
      AND top_job_limit IS NOT NULL
      AND minimum_quality_score IS NOT NULL
), ranked AS (
    SELECT
        r.*,
        p.top_job_limit,
        p.minimum_quality_score,
        row_number() OVER (
            ORDER BY
                r.overall_quality_score DESC NULLS LAST,
                r.profile_direction_score DESC NULLS LAST,
                r.evidence_quality_score DESC NULLS LAST,
                r.publication_date DESC NULLS LAST,
                r.silver_job_id
        ) AS product_rank
    FROM gold_product_v1_job_readiness r
    CROSS JOIN approved_policy p
    WHERE r.product_readiness_status = 'rankable'
      AND r.overall_quality_score >= p.minimum_quality_score
)
SELECT *
FROM ranked
WHERE product_rank <= top_job_limit;

CREATE OR REPLACE VIEW gold_product_v1_application_readiness AS
WITH source_status AS (
    SELECT
        bool_or(document_type = 'base_cv' AND status = 'approved') AS base_cv_approved,
        bool_or(document_type = 'base_application_letter' AND status = 'approved') AS base_letter_approved
    FROM application_source_documents
)
SELECT
    r.silver_job_id,
    r.title,
    r.company_name,
    r.product_readiness_status,
    s.base_cv_approved,
    s.base_letter_approved,
    CASE
        WHEN r.product_readiness_status <> 'rankable' THEN 'blocked_job_not_eligible'
        WHEN NOT coalesce(s.base_cv_approved, false) THEN 'blocked_missing_base_cv'
        WHEN NOT coalesce(s.base_letter_approved, false) THEN 'blocked_missing_base_application_letter'
        ELSE 'ready_for_generation'
    END AS application_readiness_status
FROM gold_product_v1_job_readiness r
CROSS JOIN source_status s;
