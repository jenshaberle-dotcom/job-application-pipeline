-- DEMO-001 / PRODUCT-V1-RANKING-SCORE-REVIEW-001
--
-- Persist deterministic Product V1 ranking component scores without changing the
-- employer-origin assessment revision used by capability-fit/hard-filter reviews.
-- Ranking writes therefore have their own timestamp and immutable audit binding.
-- No rank, Top-5 membership, application generation or submission authority is
-- introduced here; existing approved Product V1 policy/read models remain owners.

ALTER TABLE job_product_assessments
ADD COLUMN IF NOT EXISTS ranking_updated_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS product_v1_ranking_score_reviews (
    id BIGSERIAL PRIMARY KEY,
    silver_job_id BIGINT NOT NULL REFERENCES silver_jobs(id) ON DELETE CASCADE,
    assessment_updated_at TIMESTAMPTZ NOT NULL,
    assessment_detail_sha256 TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    rubric_version TEXT NOT NULL,
    component_scores JSONB NOT NULL,
    overall_quality_score NUMERIC(6, 2) NOT NULL,
    evidence_payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    reviewed_by TEXT NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_product_v1_ranking_review_detail_sha
        CHECK (assessment_detail_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_product_v1_ranking_review_policy
        CHECK (length(btrim(policy_version)) > 0),
    CONSTRAINT chk_product_v1_ranking_review_rubric
        CHECK (length(btrim(rubric_version)) > 0),
    CONSTRAINT chk_product_v1_ranking_review_components
        CHECK (jsonb_typeof(component_scores) = 'object'),
    CONSTRAINT chk_product_v1_ranking_review_evidence
        CHECK (jsonb_typeof(evidence_payload) = 'object'),
    CONSTRAINT chk_product_v1_ranking_review_overall
        CHECK (overall_quality_score BETWEEN 0 AND 100),
    CONSTRAINT chk_product_v1_ranking_review_status
        CHECK (status IN ('active', 'superseded')),
    CONSTRAINT chk_product_v1_ranking_review_reviewed_by
        CHECK (length(btrim(reviewed_by)) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_product_v1_ranking_score_review_active_job
ON product_v1_ranking_score_reviews (silver_job_id)
WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_product_v1_ranking_score_review_binding
ON product_v1_ranking_score_reviews (
    silver_job_id,
    assessment_updated_at,
    assessment_detail_sha256,
    policy_version,
    status
);
