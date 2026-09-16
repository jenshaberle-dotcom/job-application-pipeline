-- F4B / A1 + C1
--
-- Reaffirm PD-051 at 70/100 and introduce an exact-bound read model for the
-- existing PD-052 score as Affinity/desirability. Historical migrations remain
-- immutable. This migration does not create Candidate Fit, Combined-score,
-- Top-5 membership, application or provider authority.

DO $$
DECLARE
    current_status TEXT;
    current_threshold NUMERIC;
    current_weights JSONB;
BEGIN
    SELECT status, minimum_quality_score, ranking_weights
      INTO current_status, current_threshold, current_weights
    FROM product_v1_ranking_policy
    WHERE policy_key = 'default'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'F4B_A1_DEFAULT_POLICY_MISSING';
    END IF;
    IF current_status <> 'approved' THEN
        RAISE EXCEPTION 'F4B_A1_POLICY_NOT_APPROVED:%', current_status;
    END IF;
    IF current_threshold NOT IN (60.00, 70.00) THEN
        RAISE EXCEPTION 'F4B_A1_UNEXPECTED_THRESHOLD:%', current_threshold;
    END IF;
    IF current_weights <> '{"profile_direction": 0.40, "reliability_focus": 0.25, "data_focus": 0.20, "evidence_quality": 0.15}'::jsonb THEN
        RAISE EXCEPTION 'F4B_C1_PD052_WEIGHT_DRIFT:%', current_weights;
    END IF;

    UPDATE product_v1_ranking_policy
    SET minimum_quality_score = 70.00,
        policy_version = 'product-v1-2026-09-16-affinity-v1',
        updated_at = now()
    WHERE policy_key = 'default';
END $$;

-- Legacy table name is retained for migration compatibility. Its exact active
-- review is now the persisted deterministic PD-052 Affinity evidence. The view
-- intentionally exposes only reviews still bound to the exact current
-- assessment revision, detail fingerprint and current approved policy version.
CREATE OR REPLACE VIEW gold_product_v1_affinity AS
SELECT
    assessment.silver_job_id,
    review.overall_quality_score AS affinity_score,
    (review.component_scores ->> 'profile_direction_score')::numeric(6,2)
        AS profile_direction_score,
    (review.component_scores ->> 'reliability_focus_score')::numeric(6,2)
        AS reliability_focus_score,
    (review.component_scores ->> 'data_focus_score')::numeric(6,2)
        AS data_focus_score,
    (review.component_scores ->> 'evidence_quality_score')::numeric(6,2)
        AS evidence_quality_score,
    review.assessment_updated_at,
    review.assessment_detail_sha256,
    review.policy_version,
    review.rubric_version,
    review.evidence_payload,
    review.reviewed_at,
    'pd-052'::text AS affinity_authority,
    'authoritative'::text AS affinity_authority_status
FROM job_product_assessments assessment
JOIN product_v1_ranking_score_reviews review
  ON review.silver_job_id = assessment.silver_job_id
 AND review.status = 'active'
JOIN product_v1_ranking_policy policy
  ON policy.policy_key = 'default'
 AND policy.status = 'approved'
 AND review.policy_version = policy.policy_version
WHERE assessment.origin_validation_status = 'validated'
  AND review.assessment_updated_at = assessment.updated_at
  AND review.assessment_detail_sha256 = coalesce(
      assessment.ranking_factors ->> 'detail_description_sha256',
      ''
  );

COMMENT ON VIEW gold_product_v1_affinity IS
'F4B C1 exact-bound PD-052 Affinity/desirability authority. Affinity answers whether a job is attractive; it is not Candidate Fit, Combined score, hard-filter override or Top-5 authority.';

-- Preserve the canonical Product V1 readiness column contract from migration
-- 109, but source the four legacy score columns and overall_quality_score only
-- from exact-bound Affinity authority. This prevents stale score persistence
-- from making a job rankable after an unrelated assessment revision changes.
-- Explicit affinity_* fields are appended for the API/UI.
CREATE OR REPLACE VIEW gold_product_v1_job_readiness AS
WITH approved_policy AS (
    SELECT *
    FROM product_v1_ranking_policy
    WHERE policy_key = 'default'
), scored AS (
    SELECT
        silver.id AS silver_job_id,
        silver.title,
        silver.company_name,
        silver.city,
        silver.country,
        silver.publication_date,
        silver.source_name,
        silver.source_url,
        silver.canonical_source_type,
        assessment.origin_validation_status,
        CASE coalesce(lifecycle.lifecycle_status, 'stale_needs_refresh')
            WHEN 'active_confirmed' THEN 'active'
            WHEN 'inactive_confirmed' THEN 'inactive'
            ELSE 'unknown'
        END AS activity_status,
        coalesce(hard_filter.hard_filter_status, 'unknown') AS hard_filter_status,
        affinity.profile_direction_score,
        affinity.data_focus_score,
        affinity.reliability_focus_score,
        affinity.evidence_quality_score,
        affinity.affinity_score AS overall_quality_score,
        assessment.work_model,
        assessment.commute_minutes,
        assessment.public_transport_quality,
        assessment.explanations,
        assessment.uncertainties,
        policy.policy_key,
        policy.policy_version,
        hard_filter.hard_filter_reasons,
        hard_filter.salary_signal,
        policy.status AS ranking_policy_status,
        coalesce(lifecycle.lifecycle_status, 'stale_needs_refresh') AS lifecycle_status,
        lifecycle.last_positive_observed_at,
        lifecycle.last_health_checked_at,
        coalesce(
            lifecycle.lifecycle_evidence_reason,
            'no_explicit_health_baseline'
        ) AS lifecycle_evidence_reason,
        lifecycle.latest_health_outcome,
        lifecycle.latest_health_coverage,
        assessment.activity_status AS assessment_activity_status,
        affinity.affinity_score,
        affinity.profile_direction_score AS affinity_profile_direction_score,
        affinity.reliability_focus_score AS affinity_reliability_focus_score,
        affinity.data_focus_score AS affinity_data_focus_score,
        affinity.evidence_quality_score AS affinity_evidence_quality_score,
        coalesce(affinity.affinity_authority, 'pd-052') AS affinity_authority,
        coalesce(
            affinity.affinity_authority_status,
            'unavailable'
        ) AS affinity_authority_status
    FROM silver_jobs silver
    JOIN gold_vacancy_identity identity
      ON identity.silver_job_id = silver.id
     AND identity.is_representative
    LEFT JOIN job_product_assessments assessment
      ON assessment.silver_job_id = silver.id
    LEFT JOIN gold_product_v1_hard_filter_evaluation hard_filter
      ON hard_filter.silver_job_id = silver.id
    LEFT JOIN approved_policy policy
      ON policy.policy_key = 'default'
    LEFT JOIN gold_job_lifecycle_health lifecycle
      ON lifecycle.silver_job_id = silver.id
    LEFT JOIN gold_product_v1_affinity affinity
      ON affinity.silver_job_id = silver.id
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
    ranking_policy_status,
    lifecycle_status,
    last_positive_observed_at,
    last_health_checked_at,
    lifecycle_evidence_reason,
    latest_health_outcome,
    latest_health_coverage,
    assessment_activity_status,
    affinity_score,
    affinity_profile_direction_score,
    affinity_reliability_focus_score,
    affinity_data_focus_score,
    affinity_evidence_quality_score,
    affinity_authority,
    affinity_authority_status
FROM scored;

COMMENT ON VIEW gold_product_v1_job_readiness IS
'Canonical Product V1 readiness with exact-bound PD-052 Affinity. Legacy score fields are Affinity compatibility fields; hard gates still own rankability and Affinity is not Candidate Fit or Combined score.';
