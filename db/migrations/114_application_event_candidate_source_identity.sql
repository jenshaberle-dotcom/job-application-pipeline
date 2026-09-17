-- F5 / APP-TRACK-001 / source-message idempotency + evidence supersession
--
-- Keep immutable source-message identity separate from classifier interpretation.
-- A Gmail message may be reclassified as rules/evidence improve, but at most one
-- interpretation may be active at a time. Historical interpretations remain
-- auditable and are never promoted to submission/lifecycle authority by this
-- migration.
--
-- Boundaries:
--   * source identity is classifier-independent;
--   * evidence candidates remain evidence_only;
--   * no application_submissions or application_lifecycle_events are created;
--   * no Gmail/provider access or email/application action is introduced.

ALTER TABLE application_event_candidates
    ADD COLUMN IF NOT EXISTS source_identity_key TEXT,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS supersedes_candidate_id BIGINT;

-- Historical rows predate the source-identity contract. Preserve them without
-- inventing cross-message identity: each legacy row receives a unique legacy key.
UPDATE application_event_candidates
SET source_identity_key = 'legacy:' || id::text || ':' || evidence_fingerprint
WHERE source_identity_key IS NULL;

ALTER TABLE application_event_candidates
    ALTER COLUMN source_identity_key SET NOT NULL;

ALTER TABLE application_event_candidates
    DROP CONSTRAINT IF EXISTS uq_application_event_candidate_evidence;

ALTER TABLE application_event_candidates
    ADD CONSTRAINT chk_application_event_candidate_source_identity_nonempty CHECK (
        btrim(source_identity_key) <> ''
    ),
    ADD CONSTRAINT chk_application_event_candidate_no_self_supersede CHECK (
        supersedes_candidate_id IS NULL OR supersedes_candidate_id <> id
    ),
    ADD CONSTRAINT uq_application_event_candidate_id_source_identity UNIQUE (
        id, source_kind, source_identity_key
    ),
    ADD CONSTRAINT fk_application_event_candidate_supersedes_same_source
        FOREIGN KEY (supersedes_candidate_id, source_kind, source_identity_key)
        REFERENCES application_event_candidates(id, source_kind, source_identity_key)
        ON DELETE RESTRICT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_application_event_candidate_active_source
ON application_event_candidates (source_kind, source_identity_key)
WHERE is_active;

CREATE INDEX IF NOT EXISTS idx_application_event_candidate_interpretation
ON application_event_candidates (
    source_kind,
    source_identity_key,
    evidence_fingerprint,
    candidate_class,
    created_at DESC
);

COMMENT ON COLUMN application_event_candidates.source_identity_key IS
'Classifier-independent bounded identity for one source message. Gmail ingestion hashes source kind + mailbox-account fingerprint + hashed message reference.';

COMMENT ON COLUMN application_event_candidates.is_active IS
'Exactly one interpretation per source_identity_key may be active. Inactive rows are retained evidence history.';

COMMENT ON COLUMN application_event_candidates.supersedes_candidate_id IS
'Previous interpretation of the same source identity superseded by this candidate. Evidence-only; never lifecycle authority.';

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
        max(observed_at) AS latest_candidate_at
    FROM application_event_candidates
    WHERE matched_application_id IS NOT NULL
      AND is_active
    GROUP BY matched_application_id
), eligible_observations AS (
    SELECT
        candidate.matched_application_id AS application_id,
        candidate.candidate_class AS observed_event_class,
        candidate.observed_at,
        candidate.confidence AS observed_confidence,
        CASE candidate.candidate_class
            WHEN 'application_acknowledgement' THEN 'applied'
            WHEN 'recruiter_contact' THEN 'reply'
            WHEN 'assessment_request' THEN 'reply'
            WHEN 'interview_invitation' THEN 'interview'
            WHEN 'offer_signal' THEN 'offer'
            WHEN 'rejection' THEN 'closed'
            WHEN 'withdrawal_confirmation' THEN 'closed'
            ELSE NULL
        END AS observed_stage,
        row_number() OVER (
            PARTITION BY candidate.matched_application_id
            ORDER BY candidate.observed_at DESC, candidate.id DESC
        ) AS observation_rank
    FROM application_event_candidates candidate
    WHERE candidate.matched_application_id IS NOT NULL
      AND candidate.is_active
      AND candidate.match_status = 'exact'
      AND candidate.review_status IN ('unreviewed', 'accepted_as_evidence')
      AND candidate.confidence >= 0.95
      AND candidate.candidate_class IN (
          'application_acknowledgement',
          'recruiter_contact',
          'interview_invitation',
          'assessment_request',
          'offer_signal',
          'rejection',
          'withdrawal_confirmation'
      )
      AND coalesce(candidate.evidence_payload->>'reason_code', '') LIKE 'deterministic_%'
), latest_observation AS (
    SELECT *
    FROM eligible_observations
    WHERE observation_rank = 1
), application_base AS (
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
        END AS attention_status,
        application.discovery_kind,
        application.discovered_at
    FROM applications application
    LEFT JOIN application_submissions submission
      ON submission.application_id = application.id
    LEFT JOIN event_rollup events
      ON events.application_id = application.id
    LEFT JOIN candidate_rollup candidates
      ON candidates.application_id = application.id
)
SELECT
    base.*,
    observation.observed_stage,
    observation.observed_event_class,
    observation.observed_at,
    observation.observed_confidence,
    coalesce(observation.observed_stage, base.authoritative_stage) AS effective_stage,
    CASE
        WHEN observation.observed_stage IS NOT NULL THEN 'mailbox_observed'
        ELSE 'authoritative_fallback'
    END AS effective_stage_basis
FROM application_base base
LEFT JOIN latest_observation observation
  ON observation.application_id = base.application_id;

COMMENT ON VIEW gold_product_v1_application_tracking IS
'F5 mailbox-first tracking read model. Only active source-message interpretations participate in attention/observed-stage projection. Historical superseded candidates remain audit evidence and cannot advance authoritative lifecycle history.';
