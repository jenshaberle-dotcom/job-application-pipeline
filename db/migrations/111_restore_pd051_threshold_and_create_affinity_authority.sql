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
    (review.component_scores ->> 'profile_direction_score')::numeric
        AS profile_direction_score,
    (review.component_scores ->> 'reliability_focus_score')::numeric
        AS reliability_focus_score,
    (review.component_scores ->> 'data_focus_score')::numeric
        AS data_focus_score,
    (review.component_scores ->> 'evidence_quality_score')::numeric
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
