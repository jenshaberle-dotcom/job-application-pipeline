CREATE TABLE IF NOT EXISTS silver_processing_decisions (
    id BIGSERIAL PRIMARY KEY,

    raw_job_id BIGINT NOT NULL
        REFERENCES raw_jobs(id),

    decision TEXT NOT NULL,

    reason TEXT,

    role_matches JSONB,

    skill_matches JSONB,

    accessibility_matches JSONB,

    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (raw_job_id)
);

CREATE INDEX IF NOT EXISTS idx_silver_processing_decisions_decision
ON silver_processing_decisions(decision);
