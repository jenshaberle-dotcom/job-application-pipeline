-- JOB-LIFECYCLE-AUTHORITATIVE-POSITIVE-001
-- Reuse the existing job_observations stream as the canonical normal-ingestion
-- positive signal without reviving historical rows from before lifecycle rollout.
--
-- No connector is activated here. No historical observation is rewritten and no
-- freshness TTL is invented. Explicit job_health_observations remain the channel
-- for direct health probes, closure, authoritative absence and unverifiable state.

CREATE TABLE IF NOT EXISTS job_lifecycle_authority_epochs (
    epoch_key TEXT PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_job_lifecycle_authority_epoch_key
        CHECK (epoch_key = 'authoritative_positive_v1'),
    CONSTRAINT chk_job_lifecycle_authority_epoch_creator
        CHECK (btrim(created_by) <> '')
);

INSERT INTO job_lifecycle_authority_epochs (
    epoch_key,
    started_at,
    created_by
)
VALUES (
    'authoritative_positive_v1',
    now(),
    'migration_092'
)
ON CONFLICT (epoch_key) DO NOTHING;

COMMENT ON TABLE job_lifecycle_authority_epochs IS
'Explicit epoch after which normal job_observations may establish current activity only when persisted source evidence proves authoritative employer-origin exact-detail acquisition.';

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
      AND raw_job.raw_data ->> 'source_type'
            = 'employer_origin_career_site'
      AND coalesce(
            raw_job.raw_data #>> '{acquisition_boundary,detail_pages_fetched}',
            'false'
          ) = 'true'
      AND coalesce(
            raw_job.raw_data #>> '{detail_evidence,status_code}',
            ''
          ) ~ '^[0-9]{3}$'
      AND (
            raw_job.raw_data #>> '{detail_evidence,status_code}'
          )::integer BETWEEN 200 AND 399
      AND NULLIF(btrim(observation.source_url), '') IS NOT NULL
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

-- gold_current_job_opportunities and Product V1 readiness already consume
-- gold_job_lifecycle_health dynamically. Replacing the lifecycle view with the
-- same column contract is therefore sufficient; no ranking/application writer is
-- introduced in this migration.
