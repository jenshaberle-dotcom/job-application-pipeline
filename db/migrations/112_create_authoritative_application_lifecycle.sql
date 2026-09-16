-- F5 / APP-TRACK-001 / Slice B
--
-- Introduce a clean, append-only application/submission/lifecycle provenance
-- foundation after the real F5 Slice-A reconciliation proved that the Product
-- DB contains no persisted application drafts and no historical post-submit
-- authority that needs migration.
--
-- Authority boundaries:
--   * an application row means "prepared", never "submitted";
--   * only application_submissions is submission authority;
--   * authoritative lifecycle events require an explicit submission row;
--   * application_event_candidates is evidence only and never feeds the
--     authoritative lifecycle stage directly;
--   * authoritative lifecycle events are append-only; corrections supersede
--     prior events for the same submission instead of rewriting/deleting history;
--   * this migration performs no provider/Gmail call and creates no send or
--     automatic application-submission path.

CREATE TABLE IF NOT EXISTS applications (
    id BIGSERIAL PRIMARY KEY,
    application_key TEXT NOT NULL UNIQUE,
    silver_job_id BIGINT NOT NULL REFERENCES silver_jobs(id) ON DELETE RESTRICT,
    draft_request_id BIGINT REFERENCES application_draft_requests(id) ON DELETE SET NULL,
    prepared_by TEXT NOT NULL,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    job_identity_snapshot JSONB NOT NULL,
    job_identity_sha256 TEXT NOT NULL,
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_applications_key_nonempty CHECK (btrim(application_key) <> ''),
    CONSTRAINT chk_applications_prepared_by_nonempty CHECK (btrim(prepared_by) <> ''),
    CONSTRAINT chk_applications_job_identity_object CHECK (
        jsonb_typeof(job_identity_snapshot) = 'object'
    ),
    CONSTRAINT chk_applications_provenance_object CHECK (
        jsonb_typeof(provenance) = 'object'
    ),
    CONSTRAINT chk_applications_job_identity_sha256 CHECK (
        job_identity_sha256 ~ '^[0-9a-f]{64}$'
    )
);

CREATE INDEX IF NOT EXISTS idx_applications_silver_job
ON applications (silver_job_id, prepared_at DESC);

CREATE TABLE IF NOT EXISTS application_submissions (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT NOT NULL UNIQUE
        REFERENCES applications(id) ON DELETE RESTRICT,
    submitted_at TIMESTAMPTZ NOT NULL,
    submission_channel TEXT NOT NULL,
    authority_kind TEXT NOT NULL,
    authority_reference TEXT NOT NULL,
    confirmed_by TEXT NOT NULL,
    submission_snapshot JSONB NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_application_submission_channel CHECK (
        submission_channel IN (
            'employer_portal',
            'email',
            'external_platform',
            'manual_other'
        )
    ),
    CONSTRAINT chk_application_submission_authority CHECK (
        authority_kind IN (
            'operator_confirmation',
            'approved_authoritative_record'
        )
    ),
    CONSTRAINT chk_application_submission_reference_nonempty CHECK (
        btrim(authority_reference) <> ''
    ),
    CONSTRAINT chk_application_submission_confirmed_by_nonempty CHECK (
        btrim(confirmed_by) <> ''
    ),
    CONSTRAINT chk_application_submission_snapshot_object CHECK (
        jsonb_typeof(submission_snapshot) = 'object'
    ),
    CONSTRAINT chk_application_submission_idempotency_nonempty CHECK (
        btrim(idempotency_key) <> ''
    )
);

COMMENT ON TABLE application_submissions IS
'F5 submission authority. Presence of an application row or approved draft does not mean submitted; only an explicit row here, backed by operator confirmation or a separately approved authoritative record, establishes Applied.';

CREATE TABLE IF NOT EXISTS application_lifecycle_events (
    id BIGSERIAL PRIMARY KEY,
    submission_id BIGINT NOT NULL
        REFERENCES application_submissions(id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL,
    event_at TIMESTAMPTZ NOT NULL,
    authority_kind TEXT NOT NULL,
    authority_reference TEXT NOT NULL,
    recorded_by TEXT NOT NULL,
    event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    supersedes_event_id BIGINT,
    idempotency_key TEXT NOT NULL UNIQUE,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_application_lifecycle_event_id_submission UNIQUE (id, submission_id),
    CONSTRAINT fk_application_lifecycle_supersedes_same_submission
        FOREIGN KEY (supersedes_event_id, submission_id)
        REFERENCES application_lifecycle_events(id, submission_id)
        ON DELETE RESTRICT,
    CONSTRAINT chk_application_lifecycle_event_type CHECK (
        event_type IN (
            'application_acknowledgement_confirmed',
            'recruiter_contact_confirmed',
            'interview_invitation_confirmed',
            'assessment_request_confirmed',
            'offer_confirmed',
            'rejection_confirmed',
            'withdrawal_confirmed',
            'closed_other_confirmed'
        )
    ),
    CONSTRAINT chk_application_lifecycle_event_authority CHECK (
        authority_kind IN (
            'operator_confirmation',
            'approved_authoritative_record'
        )
    ),
    CONSTRAINT chk_application_lifecycle_event_reference_nonempty CHECK (
        btrim(authority_reference) <> ''
    ),
    CONSTRAINT chk_application_lifecycle_event_recorded_by_nonempty CHECK (
        btrim(recorded_by) <> ''
    ),
    CONSTRAINT chk_application_lifecycle_event_payload_object CHECK (
        jsonb_typeof(event_payload) = 'object'
    ),
    CONSTRAINT chk_application_lifecycle_event_idempotency_nonempty CHECK (
        btrim(idempotency_key) <> ''
    ),
    CONSTRAINT chk_application_lifecycle_no_self_supersede CHECK (
        supersedes_event_id IS NULL OR supersedes_event_id <> id
    )
);

CREATE INDEX IF NOT EXISTS idx_application_lifecycle_events_submission
ON application_lifecycle_events (submission_id, event_at DESC, id DESC);

COMMENT ON TABLE application_lifecycle_events IS
'Append-only F5 authoritative lifecycle history after submission. Every event references explicit submission authority. Corrections add a new authoritative event that may supersede an earlier event for the same submission; evidence candidates never become authoritative merely by existing.';

CREATE TABLE IF NOT EXISTS application_event_candidates (
    id BIGSERIAL PRIMARY KEY,
    matched_application_id BIGINT
        REFERENCES applications(id) ON DELETE RESTRICT,
    match_status TEXT NOT NULL,
    candidate_class TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_thread_reference TEXT,
    source_message_reference TEXT,
    evidence_fingerprint TEXT NOT NULL,
    confidence NUMERIC(5, 4),
    ambiguity_reason TEXT,
    evidence_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    review_status TEXT NOT NULL DEFAULT 'unreviewed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,
    CONSTRAINT chk_application_event_candidate_match CHECK (
        match_status IN ('exact', 'ambiguous', 'unmatched')
    ),
    CONSTRAINT chk_application_event_candidate_class CHECK (
        candidate_class IN (
            'application_acknowledgement',
            'recruiter_contact',
            'interview_invitation',
            'assessment_request',
            'offer_signal',
            'rejection',
            'withdrawal_confirmation',
            'other',
            'ambiguous'
        )
    ),
    CONSTRAINT chk_application_event_candidate_source CHECK (
        source_kind IN ('gmail', 'manual_evidence', 'runtime_evidence')
    ),
    CONSTRAINT chk_application_event_candidate_confidence CHECK (
        confidence IS NULL OR confidence BETWEEN 0 AND 1
    ),
    CONSTRAINT chk_application_event_candidate_payload_object CHECK (
        jsonb_typeof(evidence_payload) = 'object'
    ),
    CONSTRAINT chk_application_event_candidate_review_status CHECK (
        review_status IN (
            'unreviewed',
            'accepted_as_evidence',
            'dismissed',
            'ambiguous'
        )
    ),
    CONSTRAINT chk_application_event_candidate_fingerprint_nonempty CHECK (
        btrim(evidence_fingerprint) <> ''
    ),
    CONSTRAINT uq_application_event_candidate_evidence UNIQUE (
        source_kind,
        evidence_fingerprint,
        candidate_class
    )
);

CREATE INDEX IF NOT EXISTS idx_application_event_candidates_attention
ON application_event_candidates (
    review_status,
    matched_application_id,
    created_at DESC
);

COMMENT ON TABLE application_event_candidates IS
'F5 communication evidence only. Gmail/runtime/manual evidence may populate this table, but rows here cannot establish submission or mutate authoritative application lifecycle state.';

CREATE OR REPLACE VIEW gold_product_v1_application_tracking AS
WITH active_events AS (
    SELECT event.*
    FROM application_lifecycle_events event
    WHERE NOT EXISTS (
        SELECT 1
        FROM application_lifecycle_events replacement
        WHERE replacement.supersedes_event_id = event.id
          AND replacement.submission_id = event.submission_id
    )
), event_rollup AS (
    SELECT
        submission.application_id,
        count(*)::integer AS authoritative_event_count,
        max(event.event_at) AS latest_authoritative_event_at,
        bool_or(event.event_type IN (
            'application_acknowledgement_confirmed',
            'recruiter_contact_confirmed',
            'assessment_request_confirmed'
        )) AS has_reply,
        bool_or(event.event_type = 'interview_invitation_confirmed') AS has_interview,
        bool_or(event.event_type = 'offer_confirmed') AS has_offer,
        bool_or(event.event_type IN (
            'rejection_confirmed',
            'withdrawal_confirmed',
            'closed_other_confirmed'
        )) AS is_closed
    FROM active_events event
    JOIN application_submissions submission
      ON submission.id = event.submission_id
    GROUP BY submission.application_id
), candidate_rollup AS (
    SELECT
        matched_application_id AS application_id,
        count(*) FILTER (WHERE review_status IN ('unreviewed', 'ambiguous'))::integer
            AS attention_candidate_count,
        max(created_at) AS latest_candidate_at
    FROM application_event_candidates
    WHERE matched_application_id IS NOT NULL
    GROUP BY matched_application_id
)
SELECT
    application.id AS application_id,
    application.application_key,
    application.silver_job_id,
    application.draft_request_id,
    application.prepared_at,
    application.prepared_by,
    application.job_identity_snapshot,
    application.job_identity_sha256,
    submission.id AS submission_id,
    submission.submitted_at,
    submission.submission_channel,
    submission.authority_kind AS submission_authority_kind,
    submission.authority_reference AS submission_authority_reference,
    CASE
        WHEN submission.id IS NULL THEN 'prepared'
        WHEN coalesce(events.is_closed, false) THEN 'closed'
        WHEN coalesce(events.has_offer, false) THEN 'offer'
        WHEN coalesce(events.has_interview, false) THEN 'interview'
        WHEN coalesce(events.has_reply, false) THEN 'reply'
        ELSE 'applied'
    END AS authoritative_stage,
    coalesce(events.authoritative_event_count, 0) AS authoritative_event_count,
    events.latest_authoritative_event_at,
    coalesce(candidates.attention_candidate_count, 0) AS attention_candidate_count,
    candidates.latest_candidate_at,
    CASE
        WHEN coalesce(candidates.attention_candidate_count, 0) > 0
            THEN 'evidence_review_required'
        ELSE 'none'
    END AS attention_status
FROM applications application
LEFT JOIN application_submissions submission
  ON submission.application_id = application.id
LEFT JOIN event_rollup events
  ON events.application_id = application.id
LEFT JOIN candidate_rollup candidates
  ON candidates.application_id = application.id;

COMMENT ON VIEW gold_product_v1_application_tracking IS
'F5 authoritative application tracking read model. Stage derives only from prepared application identity, explicit submission authority and active authoritative lifecycle events bound to that submission. Communication candidates may surface attention but cannot advance stage.';
