-- JOB-LIFECYCLE-AUTHORITATIVE-POSITIVE-002
-- Extend the existing post-rollout positive-observation authority to the
-- explicit ATS-backed employer-origin exact-detail contract already persisted
-- by the generic SuccessFactors connector.
--
-- This does not create a new authority epoch, activate a connector, rewrite
-- Bronze history or invent freshness. The observation still has to be newer
-- than authoritative_positive_v1. Direct employer career sites keep the exact
-- migration-092 contract. ATS-backed authority additionally requires persisted
-- target-employer verification and exact raw/observation URL identity.

CREATE OR REPLACE VIEW gold_job_lifecycle_health AS
WITH authority_epoch AS (
    SELECT started_at
    FROM job_lifecycle_authority_epochs
    WHERE epoch_key = 'authoritative_positive_v1'
), historical_positive AS (
    SELECT
        raw_job_id,
        max(observed_at) AS last_positive_observed_at
    FROM job_observations
    WHERE raw_job_id IS NOT NULL
      AND is_seen = TRUE
    GROUP BY raw_job_id
), explicit_positive AS (
    SELECT
        raw_job_id,
        max(observed_at) AS last_positive_observed_at
    FROM job_health_observations
    WHERE outcome = 'seen_active'
    GROUP BY raw_job_id
), positive_union AS (
    SELECT raw_job_id, last_positive_observed_at FROM historical_positive
    UNION ALL
    SELECT raw_job_id, last_positive_observed_at FROM explicit_positive
), last_positive AS (
    SELECT
        raw_job_id,
        max(last_positive_observed_at) AS last_positive_observed_at
    FROM positive_union
    GROUP BY raw_job_id
), authoritative_positive AS (
    SELECT
        observation.raw_job_id,
        max(observation.observed_at) AS last_authoritative_positive_at
    FROM job_observations observation
    JOIN raw_jobs raw_job
      ON raw_job.id = observation.raw_job_id
     AND raw_job.source_name = observation.source_name
    CROSS JOIN authority_epoch epoch
    WHERE observation.raw_job_id IS NOT NULL
      AND observation.is_seen = TRUE
      AND observation.observed_at >= epoch.started_at
      AND (
            (
                raw_job.raw_data ->> 'source_type'
                    = 'employer_origin_career_site'
                AND coalesce(
                        raw_job.raw_data
                            #>> '{acquisition_boundary,detail_pages_fetched}',
                        'false'
                    ) = 'true'
            )
            OR
            (
                raw_job.raw_data ->> 'source_type'
                    = 'employer_origin_ats_backed_career_site'
                AND coalesce(
                        raw_job.raw_data
                            #>> '{detail_evidence,target_employer_verified}',
                        'false'
                    ) = 'true'
                AND NULLIF(
                        btrim(raw_job.raw_data #>> '{job,source_url}'),
                        ''
                    ) = NULLIF(btrim(observation.source_url), '')
            )
          )
      AND coalesce(
            raw_job.raw_data #>> '{detail_evidence,status_code}',
            ''
          ) ~ '^[0-9]{3}$'
      AND (
            raw_job.raw_data #>> '{detail_evidence,status_code}'
          )::integer BETWEEN 200 AND 399
      AND NULLIF(btrim(raw_job.source_url), '')
            = NULLIF(btrim(observation.source_url), '')
    GROUP BY observation.raw_job_id
), latest_health AS (
    SELECT DISTINCT ON (raw_job_id)
        id,
        raw_job_id,
        outcome,
        coverage,
        evidence_reason,
        observed_by,
        observed_at
    FROM job_health_observations
    ORDER BY raw_job_id, observed_at DESC, id DESC
), resolved AS (
    SELECT
        silver_job.id AS silver_job_id,
        silver_job.raw_job_id,
        silver_job.source_name,
        silver_job.external_job_id,
        positive.last_positive_observed_at,
        CASE
            WHEN authoritative.last_authoritative_positive_at IS NOT NULL
             AND (
                    health.raw_job_id IS NULL
                    OR authoritative.last_authoritative_positive_at
                        > health.observed_at
                 )
                THEN authoritative.last_authoritative_positive_at
            WHEN health.raw_job_id IS NOT NULL
                THEN health.observed_at
            ELSE NULL
        END AS last_health_checked_at,
        CASE
            WHEN authoritative.last_authoritative_positive_at IS NOT NULL
             AND (
                    health.raw_job_id IS NULL
                    OR authoritative.last_authoritative_positive_at
                        > health.observed_at
                 )
                THEN 'seen_active'
            ELSE health.outcome
        END AS latest_health_outcome,
        CASE
            WHEN authoritative.last_authoritative_positive_at IS NOT NULL
             AND (
                    health.raw_job_id IS NULL
                    OR authoritative.last_authoritative_positive_at
                        > health.observed_at
                 )
                THEN 'exact_detail'
            ELSE health.coverage
        END AS latest_health_coverage,
        CASE
            WHEN authoritative.last_authoritative_positive_at IS NOT NULL
             AND (
                    health.raw_job_id IS NULL
                    OR authoritative.last_authoritative_positive_at
                        > health.observed_at
                 )
                THEN 'active_confirmed'
            WHEN health.raw_job_id IS NULL
                THEN 'stale_needs_refresh'
            WHEN health.outcome = 'seen_active'
                THEN 'active_confirmed'
            WHEN health.outcome = 'closed'
             AND health.coverage = 'exact_detail'
                THEN 'inactive_confirmed'
            WHEN health.outcome = 'not_seen'
             AND health.coverage = 'complete_inventory'
                THEN 'inactive_confirmed'
            ELSE 'unverifiable'
        END AS lifecycle_status,
        CASE
            WHEN authoritative.last_authoritative_positive_at IS NOT NULL
             AND (
                    health.raw_job_id IS NULL
                    OR authoritative.last_authoritative_positive_at
                        > health.observed_at
                 )
                THEN 'authoritative_employer_origin_job_observation'
            WHEN health.raw_job_id IS NULL
                THEN 'no_explicit_health_baseline'
            ELSE health.evidence_reason
        END AS lifecycle_evidence_reason,
        CASE
            WHEN authoritative.last_authoritative_positive_at IS NOT NULL
             AND (
                    health.raw_job_id IS NULL
                    OR authoritative.last_authoritative_positive_at
                        > health.observed_at
                 )
                THEN 'central_job_observation_authority'
            ELSE health.observed_by
        END AS latest_health_observed_by
    FROM silver_jobs silver_job
    LEFT JOIN last_positive positive
      ON positive.raw_job_id = silver_job.raw_job_id
    LEFT JOIN authoritative_positive authoritative
      ON authoritative.raw_job_id = silver_job.raw_job_id
    LEFT JOIN latest_health health
      ON health.raw_job_id = silver_job.raw_job_id
)
SELECT *
FROM resolved;

-- Downstream views already consume gold_job_lifecycle_health through its stable
-- column contract. The fresh observation already persisted by the controlled
-- E.ON replay therefore becomes visible dynamically after this migration; no
-- connector replay or assessment/ranking mutation is required.
