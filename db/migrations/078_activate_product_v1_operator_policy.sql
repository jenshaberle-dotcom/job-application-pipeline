-- PRODUCT-V1-POLICY-001
-- Activate the operator-approved Product V1 Top-5 and hard-filter contract.
--
-- Configuration and read-model preparation only. No StepStone/provider call,
-- source activation, scheduler mutation, draft generation or submission.
--
-- Privacy boundary: the public repository records the negotiable target salary
-- of EUR 75,000 gross/year. Current compensation remains local runtime context.

ALTER TABLE product_v1_ranking_policy
ADD COLUMN IF NOT EXISTS top_job_semantics TEXT;
ALTER TABLE product_v1_ranking_policy
ADD COLUMN IF NOT EXISTS comparable_score_delta NUMERIC(6, 2);
ALTER TABLE product_v1_ranking_policy
ADD COLUMN IF NOT EXISTS policy_version TEXT;

ALTER TABLE product_v1_ranking_policy
DROP CONSTRAINT IF EXISTS chk_product_v1_ranking_top_job_semantics;
ALTER TABLE product_v1_ranking_policy
ADD CONSTRAINT chk_product_v1_ranking_top_job_semantics
CHECK (top_job_semantics IS NULL OR top_job_semantics = 'at_most_no_fill');

ALTER TABLE product_v1_ranking_policy
DROP CONSTRAINT IF EXISTS chk_product_v1_ranking_comparable_delta;
ALTER TABLE product_v1_ranking_policy
ADD CONSTRAINT chk_product_v1_ranking_comparable_delta
CHECK (
    comparable_score_delta IS NULL
    OR comparable_score_delta BETWEEN 0 AND 100
);

UPDATE product_v1_ranking_policy
SET
    status = 'approved',
    top_job_limit = 5,
    top_job_semantics = 'at_most_no_fill',
    minimum_quality_score = 70.00,
    ranking_weights = jsonb_build_object(
        'profile_direction', 0.40,
        'reliability_focus', 0.25,
        'data_focus', 0.20,
        'evidence_quality', 0.15
    ),
    comparable_score_delta = 3.00,
    explanation_mode = 'score_components_reasons_uncertainties_missing_information',
    policy_version = 'product-v1-2026-08-02',
    approved_by = 'jens',
    approved_at = TIMESTAMPTZ '2026-08-02 00:05:00+02',
    updated_at = now()
WHERE policy_key = 'default';

CREATE TABLE IF NOT EXISTS product_v1_hard_filter_policy (
    policy_key TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    permanent_employment_required BOOLEAN NOT NULL,
    accepted_languages JSONB NOT NULL,
    weekly_hours_min NUMERIC(5, 2) NOT NULL,
    weekly_hours_max NUMERIC(5, 2) NOT NULL,
    salary_treatment TEXT NOT NULL,
    target_salary_gross_eur INTEGER,
    current_compensation_storage TEXT NOT NULL,
    seniority_assessment_mode TEXT NOT NULL,
    allow_senior_title_when_capability_fit BOOLEAN NOT NULL,
    reject_junior_title_with_senior_requirements BOOLEAN NOT NULL,
    unknown_required_evidence_action TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_product_v1_hard_filter_policy_key
        CHECK (policy_key = 'default'),
    CONSTRAINT chk_product_v1_hard_filter_policy_status
        CHECK (status IN ('operator_decision_required', 'approved', 'superseded')),
    CONSTRAINT chk_product_v1_hard_filter_languages_array
        CHECK (jsonb_typeof(accepted_languages) = 'array'),
    CONSTRAINT chk_product_v1_hard_filter_hours
        CHECK (
            weekly_hours_min >= 0
            AND weekly_hours_max >= weekly_hours_min
            AND weekly_hours_max <= 80
        ),
    CONSTRAINT chk_product_v1_hard_filter_salary_treatment
        CHECK (salary_treatment = 'soft_negotiable_target'),
    CONSTRAINT chk_product_v1_hard_filter_salary_target
        CHECK (target_salary_gross_eur IS NULL OR target_salary_gross_eur > 0),
    CONSTRAINT chk_product_v1_hard_filter_compensation_storage
        CHECK (current_compensation_storage = 'local_runtime_only'),
    CONSTRAINT chk_product_v1_hard_filter_seniority_mode
        CHECK (
            seniority_assessment_mode
            = 'requirements_and_capability_fit_over_title'
        ),
    CONSTRAINT chk_product_v1_hard_filter_unknown_action
        CHECK (unknown_required_evidence_action = 'manual_review_required')
);

INSERT INTO product_v1_hard_filter_policy (
    policy_key,
    status,
    permanent_employment_required,
    accepted_languages,
    weekly_hours_min,
    weekly_hours_max,
    salary_treatment,
    target_salary_gross_eur,
    current_compensation_storage,
    seniority_assessment_mode,
    allow_senior_title_when_capability_fit,
    reject_junior_title_with_senior_requirements,
    unknown_required_evidence_action,
    policy_version,
    approved_by,
    approved_at
)
VALUES (
    'default',
    'approved',
    TRUE,
    '["de", "en"]'::jsonb,
    35.00,
    40.00,
    'soft_negotiable_target',
    75000,
    'local_runtime_only',
    'requirements_and_capability_fit_over_title',
    TRUE,
    TRUE,
    'manual_review_required',
    'product-v1-2026-08-02',
    'jens',
    TIMESTAMPTZ '2026-08-02 00:05:00+02'
)
ON CONFLICT (policy_key)
DO UPDATE SET
    status = EXCLUDED.status,
    permanent_employment_required = EXCLUDED.permanent_employment_required,
    accepted_languages = EXCLUDED.accepted_languages,
    weekly_hours_min = EXCLUDED.weekly_hours_min,
    weekly_hours_max = EXCLUDED.weekly_hours_max,
    salary_treatment = EXCLUDED.salary_treatment,
    target_salary_gross_eur = EXCLUDED.target_salary_gross_eur,
    current_compensation_storage = EXCLUDED.current_compensation_storage,
    seniority_assessment_mode = EXCLUDED.seniority_assessment_mode,
    allow_senior_title_when_capability_fit = EXCLUDED.allow_senior_title_when_capability_fit,
    reject_junior_title_with_senior_requirements = EXCLUDED.reject_junior_title_with_senior_requirements,
    unknown_required_evidence_action = EXCLUDED.unknown_required_evidence_action,
    policy_version = EXCLUDED.policy_version,
    approved_by = EXCLUDED.approved_by,
    approved_at = EXCLUDED.approved_at,
    updated_at = now();

ALTER TABLE job_product_assessments
ADD COLUMN IF NOT EXISTS employment_type TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE job_product_assessments
ADD COLUMN IF NOT EXISTS employment_evidence_status TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE job_product_assessments
ADD COLUMN IF NOT EXISTS required_languages JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE job_product_assessments
ADD COLUMN IF NOT EXISTS language_evidence_status TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE job_product_assessments
ADD COLUMN IF NOT EXISTS weekly_hours_min NUMERIC(5, 2);
ALTER TABLE job_product_assessments
ADD COLUMN IF NOT EXISTS weekly_hours_max NUMERIC(5, 2);
ALTER TABLE job_product_assessments
ADD COLUMN IF NOT EXISTS weekly_hours_evidence_status TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE job_product_assessments
ADD COLUMN IF NOT EXISTS salary_min_gross_eur INTEGER;
ALTER TABLE job_product_assessments
ADD COLUMN IF NOT EXISTS salary_max_gross_eur INTEGER;
ALTER TABLE job_product_assessments
ADD COLUMN IF NOT EXISTS salary_evidence_status TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE job_product_assessments
ADD COLUMN IF NOT EXISTS title_seniority TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE job_product_assessments
ADD COLUMN IF NOT EXISTS requirements_seniority TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE job_product_assessments
ADD COLUMN IF NOT EXISTS capability_fit_status TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE job_product_assessments
ADD COLUMN IF NOT EXISTS seniority_evidence_status TEXT NOT NULL DEFAULT 'unknown';

ALTER TABLE job_product_assessments
DROP CONSTRAINT IF EXISTS chk_job_product_employment_type;
ALTER TABLE job_product_assessments
ADD CONSTRAINT chk_job_product_employment_type CHECK (
    employment_type IN (
        'permanent', 'fixed_term', 'temporary', 'freelance',
        'internship', 'trainee', 'unknown'
    )
);
ALTER TABLE job_product_assessments
DROP CONSTRAINT IF EXISTS chk_job_product_employment_evidence;
ALTER TABLE job_product_assessments
ADD CONSTRAINT chk_job_product_employment_evidence
CHECK (employment_evidence_status IN ('observed', 'unknown'));
ALTER TABLE job_product_assessments
DROP CONSTRAINT IF EXISTS chk_job_product_required_languages_array;
ALTER TABLE job_product_assessments
ADD CONSTRAINT chk_job_product_required_languages_array
CHECK (jsonb_typeof(required_languages) = 'array');
ALTER TABLE job_product_assessments
DROP CONSTRAINT IF EXISTS chk_job_product_language_evidence;
ALTER TABLE job_product_assessments
ADD CONSTRAINT chk_job_product_language_evidence
CHECK (language_evidence_status IN ('observed', 'unknown'));
ALTER TABLE job_product_assessments
DROP CONSTRAINT IF EXISTS chk_job_product_weekly_hours;
ALTER TABLE job_product_assessments
ADD CONSTRAINT chk_job_product_weekly_hours CHECK (
    (weekly_hours_min IS NULL OR weekly_hours_min BETWEEN 0 AND 80)
    AND (weekly_hours_max IS NULL OR weekly_hours_max BETWEEN 0 AND 80)
    AND (
        weekly_hours_min IS NULL
        OR weekly_hours_max IS NULL
        OR weekly_hours_max >= weekly_hours_min
    )
);
ALTER TABLE job_product_assessments
DROP CONSTRAINT IF EXISTS chk_job_product_weekly_hours_evidence;
ALTER TABLE job_product_assessments
ADD CONSTRAINT chk_job_product_weekly_hours_evidence
CHECK (weekly_hours_evidence_status IN ('observed', 'unknown'));
ALTER TABLE job_product_assessments
DROP CONSTRAINT IF EXISTS chk_job_product_salary_values;
ALTER TABLE job_product_assessments
ADD CONSTRAINT chk_job_product_salary_values CHECK (
    (salary_min_gross_eur IS NULL OR salary_min_gross_eur > 0)
    AND (salary_max_gross_eur IS NULL OR salary_max_gross_eur > 0)
    AND (
        salary_min_gross_eur IS NULL
        OR salary_max_gross_eur IS NULL
        OR salary_max_gross_eur >= salary_min_gross_eur
    )
);
ALTER TABLE job_product_assessments
DROP CONSTRAINT IF EXISTS chk_job_product_salary_evidence;
ALTER TABLE job_product_assessments
ADD CONSTRAINT chk_job_product_salary_evidence
CHECK (salary_evidence_status IN ('observed', 'negotiable', 'unknown'));
ALTER TABLE job_product_assessments
DROP CONSTRAINT IF EXISTS chk_job_product_title_seniority;
ALTER TABLE job_product_assessments
ADD CONSTRAINT chk_job_product_title_seniority
CHECK (title_seniority IN ('junior', 'mid', 'senior', 'lead', 'principal', 'unknown'));
ALTER TABLE job_product_assessments
DROP CONSTRAINT IF EXISTS chk_job_product_requirements_seniority;
ALTER TABLE job_product_assessments
ADD CONSTRAINT chk_job_product_requirements_seniority
CHECK (requirements_seniority IN ('junior', 'mid', 'senior', 'lead', 'principal', 'unknown'));
ALTER TABLE job_product_assessments
DROP CONSTRAINT IF EXISTS chk_job_product_capability_fit;
ALTER TABLE job_product_assessments
ADD CONSTRAINT chk_job_product_capability_fit
CHECK (capability_fit_status IN ('passed', 'failed', 'unknown'));
ALTER TABLE job_product_assessments
DROP CONSTRAINT IF EXISTS chk_job_product_seniority_evidence;
ALTER TABLE job_product_assessments
ADD CONSTRAINT chk_job_product_seniority_evidence
CHECK (seniority_evidence_status IN ('observed', 'unknown'));

CREATE OR REPLACE VIEW gold_product_v1_hard_filter_evaluation AS
WITH policy AS (
    SELECT *
    FROM product_v1_hard_filter_policy
    WHERE policy_key = 'default'
      AND status = 'approved'
), evaluated AS (
    SELECT
        a.silver_job_id,
        CASE
            WHEN a.employment_evidence_status <> 'observed'
                THEN 'manual_review_required'
            WHEN p.permanent_employment_required
             AND a.employment_type <> 'permanent'
                THEN 'failed'
            ELSE 'passed'
        END AS employment_status,
        CASE
            WHEN a.language_evidence_status <> 'observed'
                THEN 'manual_review_required'
            WHEN EXISTS (
                SELECT 1
                FROM jsonb_array_elements_text(a.required_languages)
                    AS required_language(language_code)
                WHERE NOT (
                    p.accepted_languages
                    ? lower(required_language.language_code)
                )
            ) THEN 'failed'
            ELSE 'passed'
        END AS language_status,
        CASE
            WHEN a.weekly_hours_evidence_status <> 'observed'
                THEN 'manual_review_required'
            WHEN a.weekly_hours_min IS NULL
             AND a.weekly_hours_max IS NULL
                THEN 'manual_review_required'
            WHEN coalesce(a.weekly_hours_min, a.weekly_hours_max)
                    <= p.weekly_hours_max
             AND coalesce(a.weekly_hours_max, a.weekly_hours_min)
                    >= p.weekly_hours_min
                THEN 'passed'
            ELSE 'failed'
        END AS weekly_hours_status,
        CASE
            WHEN a.capability_fit_status = 'failed' THEN 'failed'
            WHEN a.capability_fit_status <> 'passed'
                THEN 'manual_review_required'
            WHEN p.reject_junior_title_with_senior_requirements
             AND a.title_seniority = 'junior'
             AND a.requirements_seniority IN ('senior', 'lead', 'principal')
                THEN 'failed'
            ELSE 'passed'
        END AS seniority_status,
        CASE
            WHEN a.salary_evidence_status = 'unknown' THEN 'unknown'
            WHEN a.salary_evidence_status = 'negotiable' THEN 'negotiable'
            WHEN a.salary_max_gross_eur IS NOT NULL
             AND a.salary_max_gross_eur < p.target_salary_gross_eur
                THEN 'below_target_review'
            WHEN coalesce(a.salary_max_gross_eur, a.salary_min_gross_eur)
                    >= p.target_salary_gross_eur
                THEN 'at_or_above_target'
            ELSE 'around_target_or_incomplete'
        END AS salary_signal,
        p.policy_version
    FROM job_product_assessments a
    CROSS JOIN policy p
)
SELECT
    silver_job_id,
    employment_status,
    language_status,
    weekly_hours_status,
    seniority_status,
    salary_signal,
    CASE
        WHEN 'failed' IN (
            employment_status,
            language_status,
            weekly_hours_status,
            seniority_status
        ) THEN 'failed'
        WHEN 'manual_review_required' IN (
            employment_status,
            language_status,
            weekly_hours_status,
            seniority_status
        ) THEN 'unknown'
        ELSE 'passed'
    END AS hard_filter_status,
    jsonb_build_object(
        'employment', employment_status,
        'languages', language_status,
        'weekly_hours', weekly_hours_status,
        'seniority_and_capability_fit', seniority_status,
        'salary_soft_signal', salary_signal
    ) AS hard_filter_reasons,
    policy_version
FROM evaluated;

-- Preserve the original 25 view columns in their exact order. New fields are
-- appended only, so CREATE OR REPLACE VIEW remains PostgreSQL-compatible.
CREATE OR REPLACE VIEW gold_product_v1_job_readiness AS
WITH approved_policy AS (
    SELECT *
    FROM product_v1_ranking_policy
    WHERE policy_key = 'default'
), scored AS (
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
        coalesce(h.hard_filter_status, 'unknown') AS hard_filter_status,
        a.profile_direction_score,
        a.data_focus_score,
        a.reliability_focus_score,
        a.evidence_quality_score,
        CASE
            WHEN p.status = 'approved'
             AND a.profile_direction_score IS NOT NULL
             AND a.data_focus_score IS NOT NULL
             AND a.reliability_focus_score IS NOT NULL
             AND a.evidence_quality_score IS NOT NULL
            THEN round(
                (
                    a.profile_direction_score
                        * (p.ranking_weights ->> 'profile_direction')::numeric
                    + a.reliability_focus_score
                        * (p.ranking_weights ->> 'reliability_focus')::numeric
                    + a.data_focus_score
                        * (p.ranking_weights ->> 'data_focus')::numeric
                    + a.evidence_quality_score
                        * (p.ranking_weights ->> 'evidence_quality')::numeric
                ) / nullif(
                    (p.ranking_weights ->> 'profile_direction')::numeric
                    + (p.ranking_weights ->> 'reliability_focus')::numeric
                    + (p.ranking_weights ->> 'data_focus')::numeric
                    + (p.ranking_weights ->> 'evidence_quality')::numeric,
                    0
                ),
                2
            )
            ELSE NULL
        END::NUMERIC(6, 2) AS overall_quality_score,
        a.work_model,
        a.commute_minutes,
        a.public_transport_quality,
        a.explanations,
        a.uncertainties,
        p.policy_key,
        p.policy_version,
        h.hard_filter_reasons,
        h.salary_signal,
        p.status AS ranking_policy_status
    FROM silver_jobs sj
    LEFT JOIN job_product_assessments a
      ON a.silver_job_id = sj.id
    LEFT JOIN gold_product_v1_hard_filter_evaluation h
      ON h.silver_job_id = sj.id
    LEFT JOIN approved_policy p
      ON p.policy_key = 'default'
)
SELECT
    silver_job_id,
    title,
    company_name,
    city,
    country,
    publication_date,
    source_name,
    source_url,
    canonical_source_type,
    origin_validation_status,
    activity_status,
    hard_filter_status,
    profile_direction_score,
    data_focus_score,
    reliability_focus_score,
    evidence_quality_score,
    overall_quality_score,
    work_model,
    commute_minutes,
    public_transport_quality,
    explanations,
    uncertainties,
    policy_key,
    policy_version,
    CASE
        WHEN origin_validation_status IS NULL THEN 'assessment_required'
        WHEN origin_validation_status = 'rejected' THEN 'blocked_origin'
        WHEN origin_validation_status = 'pending'
            THEN 'origin_validation_required'
        WHEN activity_status = 'inactive' THEN 'blocked_inactive'
        WHEN activity_status = 'unknown'
            THEN 'activity_evidence_required'
        WHEN hard_filter_status = 'failed' THEN 'blocked_hard_filter'
        WHEN hard_filter_status = 'unknown'
            THEN 'hard_filter_evidence_required'
        WHEN overall_quality_score IS NULL THEN 'assessment_required'
        WHEN ranking_policy_status <> 'approved'
            THEN 'ranking_policy_required'
        ELSE 'rankable'
    END AS product_readiness_status,
    hard_filter_reasons,
    salary_signal,
    ranking_policy_status
FROM scored;

-- Preserve the original Top-5 columns through product_rank. New diagnostics are
-- appended after them. The recursive selection mirrors the Python ranker:
-- the highest remaining score opens a three-point comparison window, and only
-- within that window may hybrid/commute/transit preferences reorder jobs.
CREATE OR REPLACE VIEW gold_product_v1_top_jobs AS
WITH RECURSIVE approved_policy AS (
    SELECT *
    FROM product_v1_ranking_policy
    WHERE policy_key = 'default'
      AND status = 'approved'
      AND top_job_limit IS NOT NULL
      AND minimum_quality_score IS NOT NULL
      AND comparable_score_delta IS NOT NULL
), candidates AS (
    SELECT
        r.*,
        p.top_job_limit,
        p.minimum_quality_score,
        p.comparable_score_delta
    FROM gold_product_v1_job_readiness r
    CROSS JOIN approved_policy p
    WHERE r.product_readiness_status = 'rankable'
      AND r.overall_quality_score >= p.minimum_quality_score
), ranked AS (
    SELECT
        selected_candidate.*,
        1::BIGINT AS product_rank,
        ARRAY[selected_candidate.silver_job_id]::BIGINT[] AS selected_ids
    FROM approved_policy p
    CROSS JOIN LATERAL (
        SELECT c.*
        FROM candidates c
        WHERE c.overall_quality_score >= (
            SELECT max(c2.overall_quality_score) FROM candidates c2
        ) - p.comparable_score_delta
        ORDER BY
            CASE WHEN c.work_model = 'hybrid' THEN 0 ELSE 1 END,
            c.commute_minutes ASC NULLS LAST,
            CASE c.public_transport_quality
                WHEN 'good' THEN 0
                WHEN 'acceptable' THEN 1
                WHEN 'unknown' THEN 2
                ELSE 3
            END,
            c.evidence_quality_score DESC NULLS LAST,
            c.overall_quality_score DESC,
            c.silver_job_id
        LIMIT 1
    ) selected_candidate

    UNION ALL

    SELECT
        selected_candidate.*,
        ranked.product_rank + 1,
        array_append(ranked.selected_ids, selected_candidate.silver_job_id)
    FROM ranked
    CROSS JOIN approved_policy p
    CROSS JOIN LATERAL (
        SELECT c.*
        FROM candidates c
        WHERE NOT (c.silver_job_id = ANY(ranked.selected_ids))
          AND c.overall_quality_score >= (
              SELECT max(c2.overall_quality_score)
              FROM candidates c2
              WHERE NOT (c2.silver_job_id = ANY(ranked.selected_ids))
          ) - p.comparable_score_delta
        ORDER BY
            CASE WHEN c.work_model = 'hybrid' THEN 0 ELSE 1 END,
            c.commute_minutes ASC NULLS LAST,
            CASE c.public_transport_quality
                WHEN 'good' THEN 0
                WHEN 'acceptable' THEN 1
                WHEN 'unknown' THEN 2
                ELSE 3
            END,
            c.evidence_quality_score DESC NULLS LAST,
            c.overall_quality_score DESC,
            c.silver_job_id
        LIMIT 1
    ) selected_candidate
    WHERE ranked.product_rank < p.top_job_limit
)
SELECT
    silver_job_id,
    title,
    company_name,
    city,
    country,
    publication_date,
    source_name,
    source_url,
    canonical_source_type,
    origin_validation_status,
    activity_status,
    hard_filter_status,
    profile_direction_score,
    data_focus_score,
    reliability_focus_score,
    evidence_quality_score,
    overall_quality_score,
    work_model,
    commute_minutes,
    public_transport_quality,
    explanations,
    uncertainties,
    policy_key,
    policy_version,
    product_readiness_status,
    top_job_limit,
    minimum_quality_score,
    product_rank,
    hard_filter_reasons,
    salary_signal,
    ranking_policy_status,
    comparable_score_delta
FROM ranked;

CREATE OR REPLACE VIEW gold_product_v1_application_readiness AS
WITH source_status AS (
    SELECT
        bool_or(document_type = 'base_cv' AND status = 'approved')
            AS base_cv_approved,
        bool_or(
            document_type = 'base_application_letter'
            AND status = 'approved'
        ) AS base_letter_approved
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
        WHEN r.product_readiness_status <> 'rankable'
            THEN 'blocked_job_not_eligible'
        WHEN NOT coalesce(s.base_cv_approved, false)
            THEN 'blocked_missing_base_cv'
        WHEN NOT coalesce(s.base_letter_approved, false)
            THEN 'blocked_missing_base_application_letter'
        ELSE 'ready_for_generation'
    END AS application_readiness_status
FROM gold_product_v1_job_readiness r
CROSS JOIN source_status s;
