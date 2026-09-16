-- F5 / APP-TRACK-001 / mailbox-first correction
--
-- Installed v1.0.38 proved that the first F5 slice was too job-centric: every
-- application required an existing Silver job and communication evidence could
-- only raise review attention. The Product requirement is mailbox-first:
-- applications may be discovered from read-only mailbox evidence even when JAP
-- has never seen the job, and clear deterministic mailbox evidence may advance
-- an observed (not authoritative) lifecycle projection.
--
-- Boundaries:
--   * Silver job identity is optional enrichment, never an application prerequisite;
--   * authoritative submission/lifecycle tables remain unchanged;
--   * mailbox evidence never rewrites authoritative history;
--   * only exact, deterministic, high-confidence evidence contributes to observed_stage;
--   * ambiguous evidence remains review-required;
--   * no mailbox network access, email action, provider call or application submission
--     is introduced by this migration.

ALTER TABLE applications
    ALTER COLUMN silver_job_id DROP NOT NULL,
    ALTER COLUMN prepared_at DROP NOT NULL,
    ALTER COLUMN prepared_by DROP NOT NULL;

ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS discovery_kind TEXT NOT NULL DEFAULT 'jap_prepared',
    ADD COLUMN IF NOT EXISTS discovered_at TIMESTAMPTZ;

UPDATE applications
SET discovered_at = COALESCE(discovered_at, prepared_at, created_at)
WHERE discovered_at IS NULL;

ALTER TABLE applications
    ALTER COLUMN discovered_at SET NOT NULL;

ALTER TABLE applications
    ADD CONSTRAINT chk_applications_discovery_kind CHECK (
        discovery_kind IN ('jap_prepared', 'mailbox_observed', 'manual_external')
    );

COMMENT ON COLUMN applications.silver_job_id IS
'Optional canonical JAP/Silver job link. Mailbox-discovered applications may exist without any known JAP job.';

COMMENT ON COLUMN applications.discovery_kind IS
'How the application identity entered JAP. mailbox_observed is allowed without a Silver job and does not itself create authoritative submission status.';

ALTER TABLE application_event_candidates
    ADD COLUMN IF NOT EXISTS observed_at TIMESTAMPTZ;

UPDATE application_event_candidates
SET observed_at = created_at
WHERE observed_at IS NULL;

ALTER TABLE application_event_candidates
    ALTER COLUMN observed_at SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_application_event_candidates_observed
ON application_event_candidates (matched_application_id, observed_at DESC, id DESC);

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
        application.discovery_kind,
        application.discovered_at,
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
'F5 mailbox-first tracking read model. Applications may exist without a Silver job. authoritative_stage remains derived only from explicit authority; observed_stage is derived automatically only from exact deterministic high-confidence communication evidence. effective_stage prefers that observed mailbox state for operator tracking without rewriting authoritative history.';
