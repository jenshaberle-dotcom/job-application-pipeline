-- ML-PILOT-001A
-- Append-only operator feedback truth for the first ML booster surface.
--
-- Purpose:
--   Capture explicit operator judgments about whether a canonical Silver job is
--   worth manual review. This is supervised label provenance, not ranking or
--   application authority.
--
-- Boundary:
-- - Does not train or execute a model.
-- - Does not change Top-5, ranking, lifecycle, source activation or applications.
-- - `unsure` is retained as evidence but is not a binary supervised target.
-- - Historical labels are append-only; corrections create a new event.

CREATE TABLE IF NOT EXISTS job_review_relevance_label_events (
    id BIGSERIAL PRIMARY KEY,
    silver_job_id BIGINT NOT NULL REFERENCES silver_jobs(id) ON DELETE RESTRICT,
    label TEXT NOT NULL,
    label_contract_version TEXT NOT NULL DEFAULT 'operator-review-relevance/v1',
    reviewed_by TEXT NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    evidence_cutoff TIMESTAMPTZ NOT NULL,
    job_evidence_fingerprint TEXT NOT NULL,
    selection_reason TEXT NOT NULL DEFAULT 'normal_review',
    capture_surface TEXT NOT NULL DEFAULT 'control_center',
    deterministic_signal_visible BOOLEAN NOT NULL DEFAULT FALSE,
    ml_signal_visible BOOLEAN NOT NULL DEFAULT FALSE,
    llm_signal_visible BOOLEAN NOT NULL DEFAULT FALSE,
    active_ml_artifact_id TEXT,
    active_ml_score NUMERIC(10, 8),
    operator_note TEXT,
    supersedes_label_event_id BIGINT REFERENCES job_review_relevance_label_events(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_job_review_relevance_label
        CHECK (label IN ('interesting', 'not_relevant', 'unsure')),
    CONSTRAINT chk_job_review_relevance_contract
        CHECK (length(trim(label_contract_version)) > 0),
    CONSTRAINT chk_job_review_relevance_reviewer
        CHECK (length(trim(reviewed_by)) > 0),
    CONSTRAINT chk_job_review_relevance_fingerprint
        CHECK (job_evidence_fingerprint ~ '^sha256:[0-9a-f]{64}$'),
    CONSTRAINT chk_job_review_relevance_selection_reason
        CHECK (
            selection_reason IN (
                'normal_review',
                'ml_uncertainty',
                'signal_disagreement',
                'exploration_random',
                'tail_sample',
                'blind_holdout'
            )
        ),
    CONSTRAINT chk_job_review_relevance_capture_surface
        CHECK (capture_surface IN ('control_center', 'cli', 'operator_import')),
    CONSTRAINT chk_job_review_relevance_ml_score
        CHECK (active_ml_score IS NULL OR (active_ml_score >= 0 AND active_ml_score <= 1)),
    CONSTRAINT chk_job_review_relevance_ml_artifact
        CHECK (active_ml_artifact_id IS NULL OR length(trim(active_ml_artifact_id)) > 0),
    CONSTRAINT chk_job_review_relevance_supersedes_self
        CHECK (supersedes_label_event_id IS NULL OR supersedes_label_event_id <> id)
);

CREATE INDEX IF NOT EXISTS idx_job_review_relevance_label_events_job
ON job_review_relevance_label_events (silver_job_id, reviewed_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_job_review_relevance_label_events_label
ON job_review_relevance_label_events (label, reviewed_at DESC);

CREATE INDEX IF NOT EXISTS idx_job_review_relevance_label_events_selection
ON job_review_relevance_label_events (selection_reason, reviewed_at DESC);

CREATE OR REPLACE FUNCTION reject_job_review_relevance_label_event_mutation()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'job_review_relevance_label_events are append-only; append a superseding event instead';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_job_review_relevance_label_events_append_only
ON job_review_relevance_label_events;

CREATE TRIGGER trg_job_review_relevance_label_events_append_only
BEFORE UPDATE OR DELETE ON job_review_relevance_label_events
FOR EACH ROW
EXECUTE FUNCTION reject_job_review_relevance_label_event_mutation();

CREATE OR REPLACE VIEW gold_job_review_relevance_labels AS
WITH latest AS (
    SELECT DISTINCT ON (silver_job_id)
        id AS label_event_id,
        silver_job_id,
        label,
        label_contract_version,
        reviewed_by,
        reviewed_at,
        evidence_cutoff,
        job_evidence_fingerprint,
        selection_reason,
        capture_surface,
        deterministic_signal_visible,
        ml_signal_visible,
        llm_signal_visible,
        active_ml_artifact_id,
        active_ml_score,
        operator_note,
        supersedes_label_event_id
    FROM job_review_relevance_label_events
    ORDER BY silver_job_id, reviewed_at DESC, id DESC
)
SELECT
    latest.*,
    CASE
        WHEN label = 'interesting' THEN 1
        WHEN label = 'not_relevant' THEN 0
        ELSE NULL
    END AS supervised_target,
    label IN ('interesting', 'not_relevant') AS training_eligible
FROM latest;

COMMENT ON TABLE job_review_relevance_label_events IS
    'Append-only explicit operator labels for ML-PILOT-001 job review relevance; never model or product authority.';

COMMENT ON VIEW gold_job_review_relevance_labels IS
    'Latest operator review relevance label per Silver job; unsure remains non-training evidence.';
