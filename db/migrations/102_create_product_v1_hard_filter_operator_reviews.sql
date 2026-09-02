-- DEMO-001 / PRODUCT-V1-HARD-FILTER-REVIEW-001
-- Make the already-approved `manual_review_required` hard-filter policy executable
-- without weakening deterministic failures or inventing missing source facts.
--
-- A review is valid only for the exact current job_product_assessments.updated_at
-- and approved hard-filter policy version. It may resolve only deterministic
-- UNKNOWN after candidate capability fit has independently reached `passed`.
-- A deterministic failed component can never be overridden to passed.

CREATE TABLE IF NOT EXISTS product_v1_hard_filter_reviews (
    id BIGSERIAL PRIMARY KEY,
    silver_job_id BIGINT NOT NULL REFERENCES silver_jobs(id) ON DELETE CASCADE,
    decision TEXT NOT NULL,
    rationale TEXT NOT NULL,
    reviewed_unknown_components JSONB NOT NULL DEFAULT '[]'::jsonb,
    assessment_updated_at TIMESTAMPTZ NOT NULL,
    policy_version TEXT NOT NULL,
    review_scope TEXT NOT NULL DEFAULT 'resolve_unknown_source_evidence',
    status TEXT NOT NULL DEFAULT 'active',
    reviewed_by TEXT NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_product_v1_hard_filter_review_decision
        CHECK (decision IN ('passed', 'failed')),
    CONSTRAINT chk_product_v1_hard_filter_review_rationale
        CHECK (length(btrim(rationale)) >= 8),
    CONSTRAINT chk_product_v1_hard_filter_review_components
        CHECK (jsonb_typeof(reviewed_unknown_components) = 'array'),
    CONSTRAINT chk_product_v1_hard_filter_review_scope
        CHECK (review_scope = 'resolve_unknown_source_evidence'),
    CONSTRAINT chk_product_v1_hard_filter_review_status
        CHECK (status IN ('active', 'superseded'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_product_v1_hard_filter_review_active_job
ON product_v1_hard_filter_reviews (silver_job_id)
WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_product_v1_hard_filter_review_version
ON product_v1_hard_filter_reviews (
    silver_job_id,
    assessment_updated_at,
    policy_version,
    status
);

-- Keep the original first nine columns of gold_product_v1_hard_filter_evaluation
-- in their exact order; append review diagnostics only after policy_version.
CREATE OR REPLACE VIEW gold_product_v1_hard_filter_evaluation AS
WITH policy AS (
    SELECT *
    FROM product_v1_hard_filter_policy
    WHERE policy_key = 'default'
      AND status = 'approved'
), evaluated AS (
    SELECT
        a.silver_job_id,
        a.updated_at AS assessment_updated_at,
        a.capability_fit_status,
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
), deterministic AS (
    SELECT
        e.*,
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
        END AS deterministic_hard_filter_status
    FROM evaluated e
), active_review AS (
    SELECT
        silver_job_id,
        decision,
        rationale,
        reviewed_unknown_components,
        assessment_updated_at,
        policy_version,
        reviewed_by,
        reviewed_at
    FROM product_v1_hard_filter_reviews
    WHERE status = 'active'
      AND review_scope = 'resolve_unknown_source_evidence'
)
SELECT
    d.silver_job_id,
    d.employment_status,
    d.language_status,
    d.weekly_hours_status,
    d.seniority_status,
    d.salary_signal,
    CASE
        WHEN d.deterministic_hard_filter_status IN ('passed', 'failed')
            THEN d.deterministic_hard_filter_status
        WHEN d.capability_fit_status <> 'passed'
            THEN 'unknown'
        WHEN r.silver_job_id IS NOT NULL
         AND r.assessment_updated_at = d.assessment_updated_at
         AND r.policy_version = d.policy_version
            THEN r.decision
        ELSE 'unknown'
    END AS hard_filter_status,
    jsonb_build_object(
        'employment', d.employment_status,
        'languages', d.language_status,
        'weekly_hours', d.weekly_hours_status,
        'seniority_and_capability_fit', d.seniority_status,
        'salary_soft_signal', d.salary_signal,
        'deterministic_hard_filter_status', d.deterministic_hard_filter_status,
        'operator_review', CASE
            WHEN r.silver_job_id IS NOT NULL
             AND r.assessment_updated_at = d.assessment_updated_at
             AND r.policy_version = d.policy_version
            THEN jsonb_build_object(
                'decision', r.decision,
                'rationale', r.rationale,
                'reviewed_unknown_components', r.reviewed_unknown_components,
                'reviewed_by', r.reviewed_by,
                'reviewed_at', r.reviewed_at,
                'assessment_updated_at', r.assessment_updated_at,
                'policy_version', r.policy_version,
                'valid_for_current_assessment',
                    d.deterministic_hard_filter_status = 'unknown'
                    AND d.capability_fit_status = 'passed'
            )
            ELSE NULL
        END
    ) AS hard_filter_reasons,
    d.policy_version,
    d.deterministic_hard_filter_status,
    CASE
        WHEN d.deterministic_hard_filter_status <> 'unknown' THEN NULL
        WHEN d.capability_fit_status <> 'passed' THEN NULL
        WHEN r.silver_job_id IS NOT NULL
         AND r.assessment_updated_at = d.assessment_updated_at
         AND r.policy_version = d.policy_version
            THEN r.decision
        ELSE NULL
    END AS operator_review_decision,
    CASE
        WHEN d.deterministic_hard_filter_status = 'unknown'
         AND d.capability_fit_status = 'passed'
         AND r.silver_job_id IS NOT NULL
         AND r.assessment_updated_at = d.assessment_updated_at
         AND r.policy_version = d.policy_version
            THEN TRUE
        ELSE FALSE
    END AS operator_review_valid,
    r.reviewed_by AS operator_reviewed_by,
    r.reviewed_at AS operator_reviewed_at
FROM deterministic d
LEFT JOIN active_review r
  ON r.silver_job_id = d.silver_job_id;
