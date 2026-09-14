-- F4A-R3 Bronze2E requirement-evidence sidecar.
--
-- This migration is schema-only. It does not backfill rows, change Product
-- decisions, touch Candidate Facts, ranking, Top-5 or application state.

CREATE TABLE IF NOT EXISTS silver_job_requirement_evidence (
    silver_job_id BIGINT PRIMARY KEY REFERENCES silver_jobs(id) ON DELETE CASCADE,
    raw_job_id BIGINT NOT NULL REFERENCES raw_jobs(id) ON DELETE CASCADE,
    evidence_schema TEXT NOT NULL,
    source_evidence_schema TEXT,
    parser_family TEXT NOT NULL,
    evidence_hash TEXT NOT NULL,
    evidence_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT silver_job_requirement_evidence_hash_nonempty
        CHECK (btrim(evidence_hash) <> ''),
    CONSTRAINT silver_job_requirement_evidence_payload_object
        CHECK (jsonb_typeof(evidence_payload) = 'object'),
    CONSTRAINT silver_job_requirement_evidence_no_raw_html
        CHECK (COALESCE((evidence_payload ->> 'raw_html_persisted')::boolean, FALSE) = FALSE)
);

CREATE INDEX IF NOT EXISTS idx_silver_job_requirement_evidence_raw_job
    ON silver_job_requirement_evidence(raw_job_id);

CREATE INDEX IF NOT EXISTS idx_silver_job_requirement_evidence_parser_family
    ON silver_job_requirement_evidence(parser_family);
