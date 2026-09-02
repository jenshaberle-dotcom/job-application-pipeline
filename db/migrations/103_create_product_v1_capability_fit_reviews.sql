-- DEMO-001 / PRODUCT-V1-CAPABILITY-FIT-REVIEW-001
--
-- Persist an operator-reviewed Candidate Fact -> vacancy capability-fit decision
-- without creating a second ranking or application authority. The review is bound
-- to the exact approved Candidate Fact profile hash, exact current assessment
-- version and exact assessment detail fingerprint. Applying a review updates only
-- job_product_assessments.capability_fit_status; normal Product V1 hard-filter
-- policy remains authoritative and deterministic failures cannot be bypassed.

CREATE TABLE IF NOT EXISTS product_v1_capability_fit_reviews (
    id BIGSERIAL PRIMARY KEY,
    silver_job_id BIGINT NOT NULL REFERENCES silver_jobs(id) ON DELETE CASCADE,
    decision TEXT NOT NULL,
    rationale TEXT NOT NULL,
    candidate_profile_version TEXT NOT NULL,
    candidate_profile_sha256 TEXT NOT NULL,
    assessment_detail_sha256 TEXT NOT NULL,
    assessment_updated_at TIMESTAMPTZ NOT NULL,
    referenced_fact_keys JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'active',
    reviewed_by TEXT NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_product_v1_capability_fit_review_decision
        CHECK (decision IN ('passed', 'failed')),
    CONSTRAINT chk_product_v1_capability_fit_review_rationale
        CHECK (length(btrim(rationale)) >= 8),
    CONSTRAINT chk_product_v1_capability_fit_review_profile_version
        CHECK (length(btrim(candidate_profile_version)) > 0),
    CONSTRAINT chk_product_v1_capability_fit_review_profile_sha
        CHECK (candidate_profile_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_product_v1_capability_fit_review_detail_sha
        CHECK (assessment_detail_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_product_v1_capability_fit_review_fact_keys
        CHECK (jsonb_typeof(referenced_fact_keys) = 'array'),
    CONSTRAINT chk_product_v1_capability_fit_review_status
        CHECK (status IN ('active', 'superseded')),
    CONSTRAINT chk_product_v1_capability_fit_review_reviewed_by
        CHECK (length(btrim(reviewed_by)) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_product_v1_capability_fit_review_active_job
ON product_v1_capability_fit_reviews (silver_job_id)
WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_product_v1_capability_fit_review_binding
ON product_v1_capability_fit_reviews (
    silver_job_id,
    candidate_profile_sha256,
    assessment_updated_at,
    status
);
