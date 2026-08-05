-- EON-PRODUCT-V1-SOURCE-EVIDENCE-REFRESH-001
-- Preserve immutable before/after evidence whenever a persisted Product V1
-- assessment is refreshed from newly projected source evidence.
--
-- Schema only. This migration does not update an assessment, run a source,
-- call a provider, change ranking/readiness, or perform an application action.

CREATE TABLE IF NOT EXISTS job_product_assessment_revisions (
    id BIGSERIAL PRIMARY KEY,
    silver_job_id BIGINT NOT NULL REFERENCES silver_jobs(id) ON DELETE CASCADE,
    revision_key TEXT NOT NULL,
    previous_payload JSONB NOT NULL,
    next_payload JSONB NOT NULL,
    source_evidence JSONB NOT NULL,
    applied_by TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_job_product_assessment_revision
        UNIQUE (silver_job_id, revision_key),
    CONSTRAINT chk_job_product_assessment_revision_key
        CHECK (length(trim(revision_key)) > 0),
    CONSTRAINT chk_job_product_assessment_revision_previous_object
        CHECK (jsonb_typeof(previous_payload) = 'object'),
    CONSTRAINT chk_job_product_assessment_revision_next_object
        CHECK (jsonb_typeof(next_payload) = 'object'),
    CONSTRAINT chk_job_product_assessment_revision_source_object
        CHECK (jsonb_typeof(source_evidence) = 'object'),
    CONSTRAINT chk_job_product_assessment_revision_applied_by
        CHECK (length(trim(applied_by)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_job_product_assessment_revisions_job
ON job_product_assessment_revisions (silver_job_id, applied_at DESC, id DESC);
