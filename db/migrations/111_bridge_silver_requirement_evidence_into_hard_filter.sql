-- F4B / HARD-FILTER-SILVER-BRIDGE-001
--
-- Make the canonical Silver Bronze2E requirement sidecar the primary current
-- vacancy-evidence input to the Product hard-filter view without granting it
-- Candidate Fact, capability-fit, ranking, Top-5 or application authority.
--
-- Only conflict-free `observed_bounded_text` sidecar fields are treated as
-- observed. `source_absent`, `origin_unavailable`, conflicted or malformed fields
-- remain manual-review-required. When a sidecar exists, legacy assessment fields
-- are not used as fallback authority for the same job-source requirement.
--
-- Manual hard-filter reviews are additionally bound to the exact current sidecar
-- evidence hash. A sidecar revision therefore invalidates an older review.

ALTER TABLE product_v1_hard_filter_reviews
    ADD COLUMN IF NOT EXISTS requirement_evidence_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_product_v1_hard_filter_review_evidence_hash
ON product_v1_hard_filter_reviews (
    silver_job_id,
    requirement_evidence_hash,
    status
);

CREATE OR REPLACE FUNCTION bind_product_v1_hard_filter_review_requirement_hash()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    SELECT evidence_hash
      INTO NEW.requirement_evidence_hash
      FROM silver_job_requirement_evidence
     WHERE silver_job_id = NEW.silver_job_id;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_bind_product_v1_hard_filter_review_requirement_hash
ON product_v1_hard_filter_reviews;

CREATE TRIGGER trg_bind_product_v1_hard_filter_review_requirement_hash
BEFORE INSERT OR UPDATE OF silver_job_id, status
ON product_v1_hard_filter_reviews
FOR EACH ROW
WHEN (NEW.status = 'active')
EXECUTE FUNCTION bind_product_v1_hard_filter_review_requirement_hash();

CREATE OR REPLACE FUNCTION supersede_product_v1_hard_filter_review_on_requirement_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE product_v1_hard_filter_reviews
       SET status = 'superseded',
           updated_at = now()
     WHERE silver_job_id = NEW.silver_job_id
       AND status = 'active'
       AND requirement_evidence_hash IS DISTINCT FROM NEW.evidence_hash;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_supersede_hard_filter_review_on_requirement_change
ON silver_job_requirement_evidence;

CREATE TRIGGER trg_supersede_hard_filter_review_on_requirement_change
AFTER INSERT OR UPDATE OF evidence_hash
ON silver_job_requirement_evidence
FOR EACH ROW
EXECUTE FUNCTION supersede_product_v1_hard_filter_review_on_requirement_change();

-- Existing active reviews predate sidecar-hash binding. Fail closed rather than
-- silently grandfathering them across the new authority boundary.
UPDATE product_v1_hard_filter_reviews review
   SET status = 'superseded',
       updated_at = now()
  FROM silver_job_requirement_evidence sidecar
 WHERE review.silver_job_id = sidecar.silver_job_id
   AND review.status = 'active'
   AND review.requirement_evidence_hash IS DISTINCT FROM sidecar.evidence_hash;

CREATE OR REPLACE VIEW gold_product_v1_hard_filter_evaluation AS
WITH policy AS (
    SELECT *
    FROM product_v1_hard_filter_policy
    WHERE policy_key = 'default'
      AND status = 'approved'
), source_evidence AS (
    SELECT
        a.*,
        sidecar.evidence_hash AS requirement_evidence_hash,
        CASE
            WHEN sidecar.silver_job_id IS NOT NULL THEN 'silver_job_requirement_evidence'
            ELSE 'legacy_product_assessment'
        END AS requirement_evidence_source,
        CASE
            WHEN sidecar.silver_job_id IS NULL THEN a.employment_evidence_status = 'observed'
            WHEN sidecar.evidence_payload ->> 'schema' = 'silver_job_requirement_evidence.v1'
             AND sidecar.evidence_payload #>> '{fields,employment_type,status}' = 'observed_bounded_text'
             AND NOT (COALESCE(sidecar.evidence_payload -> 'conflicted_fields', '[]'::jsonb) ? 'employment_type')
                THEN TRUE
            ELSE FALSE
        END AS effective_employment_observed,
        CASE
            WHEN sidecar.silver_job_id IS NULL THEN a.employment_type
            WHEN sidecar.evidence_payload ->> 'schema' = 'silver_job_requirement_evidence.v1'
             AND sidecar.evidence_payload #>> '{fields,employment_type,status}' = 'observed_bounded_text'
             AND NOT (COALESCE(sidecar.evidence_payload -> 'conflicted_fields', '[]'::jsonb) ? 'employment_type')
                THEN NULLIF(sidecar.evidence_payload #>> '{fields,employment_type,value}', '')
            ELSE NULL
        END AS effective_employment_type,
        CASE
            WHEN sidecar.silver_job_id IS NULL THEN a.language_evidence_status = 'observed'
            WHEN sidecar.evidence_payload ->> 'schema' = 'silver_job_requirement_evidence.v1'
             AND sidecar.evidence_payload #>> '{fields,required_languages,status}' = 'observed_bounded_text'
             AND NOT (COALESCE(sidecar.evidence_payload -> 'conflicted_fields', '[]'::jsonb) ? 'required_languages')
                THEN TRUE
            ELSE FALSE
        END AS effective_languages_observed,
        CASE
            WHEN sidecar.silver_job_id IS NULL THEN a.required_languages
            WHEN sidecar.evidence_payload ->> 'schema' = 'silver_job_requirement_evidence.v1'
             AND sidecar.evidence_payload #>> '{fields,required_languages,status}' = 'observed_bounded_text'
             AND NOT (COALESCE(sidecar.evidence_payload -> 'conflicted_fields', '[]'::jsonb) ? 'required_languages')
                THEN COALESCE(
                    sidecar.evidence_payload #> '{fields,required_languages,values}',
                    '[]'::jsonb
                )
            ELSE '[]'::jsonb
        END AS effective_required_languages,
        CASE
            WHEN sidecar.silver_job_id IS NULL THEN a.weekly_hours_evidence_status = 'observed'
            WHEN sidecar.evidence_payload ->> 'schema' = 'silver_job_requirement_evidence.v1'
             AND sidecar.evidence_payload #>> '{fields,weekly_hours,status}' = 'observed_bounded_text'
             AND NOT (COALESCE(sidecar.evidence_payload -> 'conflicted_fields', '[]'::jsonb) ? 'weekly_hours')
             AND (
                 jsonb_typeof(sidecar.evidence_payload #> '{fields,weekly_hours,minimum}') = 'number'
                 OR jsonb_typeof(sidecar.evidence_payload #> '{fields,weekly_hours,maximum}') = 'number'
             )
                THEN TRUE
            ELSE FALSE
        END AS effective_weekly_hours_observed,
        CASE
            WHEN sidecar.silver_job_id IS NULL THEN a.weekly_hours_min
            WHEN jsonb_typeof(sidecar.evidence_payload #> '{fields,weekly_hours,minimum}') = 'number'
                THEN (sidecar.evidence_payload #>> '{fields,weekly_hours,minimum}')::numeric
            ELSE NULL
        END AS effective_weekly_hours_min,
        CASE
            WHEN sidecar.silver_job_id IS NULL THEN a.weekly_hours_max
            WHEN jsonb_typeof(sidecar.evidence_payload #> '{fields,weekly_hours,maximum}') = 'number'
                THEN (sidecar.evidence_payload #>> '{fields,weekly_hours,maximum}')::numeric
            ELSE NULL
        END AS effective_weekly_hours_max,
        CASE
            WHEN sidecar.silver_job_id IS NULL THEN a.seniority_evidence_status = 'observed'
            WHEN sidecar.evidence_payload ->> 'schema' = 'silver_job_requirement_evidence.v1'
             AND sidecar.evidence_payload #>> '{fields,requirements_seniority,status}' = 'observed_bounded_text'
             AND NOT (COALESCE(sidecar.evidence_payload -> 'conflicted_fields', '[]'::jsonb) ? 'requirements_seniority')
                THEN TRUE
            ELSE FALSE
        END AS effective_requirements_seniority_observed,
        CASE
            WHEN sidecar.silver_job_id IS NULL THEN a.requirements_seniority
            WHEN sidecar.evidence_payload ->> 'schema' = 'silver_job_requirement_evidence.v1'
             AND sidecar.evidence_payload #>> '{fields,requirements_seniority,status}' = 'observed_bounded_text'
             AND NOT (COALESCE(sidecar.evidence_payload -> 'conflicted_fields', '[]'::jsonb) ? 'requirements_seniority')
                THEN NULLIF(sidecar.evidence_payload #>> '{fields,requirements_seniority,value}', '')
            ELSE NULL
        END AS effective_requirements_seniority
    FROM job_product_assessments a
    LEFT JOIN silver_job_requirement_evidence sidecar
      ON sidecar.silver_job_id = a.silver_job_id
), evaluated AS (
    SELECT
        e.silver_job_id,
        e.updated_at AS assessment_updated_at,
        e.capability_fit_status,
        e.requirement_evidence_hash,
        e.requirement_evidence_source,
        CASE
            WHEN NOT e.effective_employment_observed
                THEN 'manual_review_required'
            WHEN p.permanent_employment_required
             AND e.effective_employment_type <> 'permanent'
                THEN 'failed'
            ELSE 'passed'
        END AS employment_status,
        CASE
            WHEN NOT e.effective_languages_observed
                THEN 'manual_review_required'
            WHEN EXISTS (
                SELECT 1
                FROM jsonb_array_elements_text(e.effective_required_languages)
                    AS required_language(language_code)
                WHERE NOT (
                    p.accepted_languages
                    ? lower(required_language.language_code)
                )
            ) THEN 'failed'
            ELSE 'passed'
        END AS language_status,
        CASE
            WHEN NOT e.effective_weekly_hours_observed
                THEN 'manual_review_required'
            WHEN e.effective_weekly_hours_min IS NULL
             AND e.effective_weekly_hours_max IS NULL
                THEN 'manual_review_required'
            WHEN coalesce(e.effective_weekly_hours_min, e.effective_weekly_hours_max)
                    <= p.weekly_hours_max
             AND coalesce(e.effective_weekly_hours_max, e.effective_weekly_hours_min)
                    >= p.weekly_hours_min
                THEN 'passed'
            ELSE 'failed'
        END AS weekly_hours_status,
        CASE
            WHEN e.capability_fit_status = 'failed' THEN 'failed'
            WHEN e.capability_fit_status <> 'passed'
                THEN 'manual_review_required'
            WHEN p.reject_junior_title_with_senior_requirements
             AND e.title_seniority = 'junior'
             AND e.effective_requirements_seniority IN ('senior', 'lead', 'principal')
                THEN 'failed'
            ELSE 'passed'
        END AS seniority_status,
        CASE
            WHEN e.salary_evidence_status = 'unknown' THEN 'unknown'
            WHEN e.salary_evidence_status = 'negotiable' THEN 'negotiable'
            WHEN e.salary_max_gross_eur IS NOT NULL
             AND e.salary_max_gross_eur < p.target_salary_gross_eur
                THEN 'below_target_review'
            WHEN coalesce(e.salary_max_gross_eur, e.salary_min_gross_eur)
                    >= p.target_salary_gross_eur
                THEN 'at_or_above_target'
            ELSE 'around_target_or_incomplete'
        END AS salary_signal,
        p.policy_version
    FROM source_evidence e
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
        requirement_evidence_hash,
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
         AND r.requirement_evidence_hash IS NOT DISTINCT FROM d.requirement_evidence_hash
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
        'requirement_evidence_source', d.requirement_evidence_source,
        'requirement_evidence_hash', d.requirement_evidence_hash,
        'operator_review', CASE
            WHEN r.silver_job_id IS NOT NULL
             AND r.assessment_updated_at = d.assessment_updated_at
             AND r.policy_version = d.policy_version
             AND r.requirement_evidence_hash IS NOT DISTINCT FROM d.requirement_evidence_hash
            THEN jsonb_build_object(
                'decision', r.decision,
                'rationale', r.rationale,
                'reviewed_unknown_components', r.reviewed_unknown_components,
                'reviewed_by', r.reviewed_by,
                'reviewed_at', r.reviewed_at,
                'assessment_updated_at', r.assessment_updated_at,
                'policy_version', r.policy_version,
                'requirement_evidence_hash', r.requirement_evidence_hash,
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
         AND r.requirement_evidence_hash IS NOT DISTINCT FROM d.requirement_evidence_hash
            THEN r.decision
        ELSE NULL
    END AS operator_review_decision,
    CASE
        WHEN d.deterministic_hard_filter_status = 'unknown'
         AND d.capability_fit_status = 'passed'
         AND r.silver_job_id IS NOT NULL
         AND r.assessment_updated_at = d.assessment_updated_at
         AND r.policy_version = d.policy_version
         AND r.requirement_evidence_hash IS NOT DISTINCT FROM d.requirement_evidence_hash
            THEN TRUE
        ELSE FALSE
    END AS operator_review_valid,
    r.reviewed_by AS operator_reviewed_by,
    r.reviewed_at AS operator_reviewed_at,
    d.requirement_evidence_hash,
    d.requirement_evidence_source
FROM deterministic d
LEFT JOIN active_review r
  ON r.silver_job_id = d.silver_job_id;
