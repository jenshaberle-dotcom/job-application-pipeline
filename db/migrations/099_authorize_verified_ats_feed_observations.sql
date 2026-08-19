-- JOB-LIFECYCLE-AUTHORITATIVE-POSITIVE-003
--
-- Recurring full-feed connectors deduplicate raw_jobs by source-local identity.
-- Current per-sighting evidence therefore lives on job_observations.normalized_evidence
-- (migration 097), not by rewriting the original Bronze row.
--
-- This migration preserves the migration-093 exact-detail authority paths and adds
-- one narrow current-observation path for reviewed, deterministically validated
-- Personio full inventories. It does not grant authority to generic Personio hosts,
-- sensor/aggregator sources, unreviewed targets, or model/provider output.

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
), authoritative_positive_candidates AS (
    SELECT
        observation.raw_job_id,
        observation.observed_at,
        CASE
            WHEN observation.normalized_evidence
                    #>> '{raw_evidence,ats_feed_authority,authority_validated}'
                    = 'true'
                THEN 'complete_inventory'
            ELSE 'exact_detail'
        END AS authority_coverage,
        CASE
            WHEN observation.normalized_evidence
                    #>> '{raw_evidence,ats_feed_authority,authority_validated}'
                    = 'true'
                THEN 'authoritative_verified_ats_feed_observation'
            ELSE 'authoritative_employer_origin_job_observation'
        END AS authority_reason
    FROM job_observations observation
    JOIN raw_jobs raw_job
      ON raw_job.id = observation.raw_job_id
     AND raw_job.source_name = observation.source_name
    CROSS JOIN authority_epoch epoch
    WHERE observation.raw_job_id IS NOT NULL
      AND observation.is_seen = TRUE
      AND observation.observed_at >= epoch.started_at
      AND (
            -- Existing direct employer-origin exact-detail authority (migration 092).
            (
                raw_job.raw_data ->> 'source_type'
                    = 'employer_origin_career_site'
                AND coalesce(
                        raw_job.raw_data
                            #>> '{acquisition_boundary,detail_pages_fetched}',
                        'false'
                    ) = 'true'
                AND NULLIF(btrim(observation.source_url), '') IS NOT NULL
                AND coalesce(
                        raw_job.raw_data #>> '{detail_evidence,status_code}',
                        ''
                    ) ~ '^[0-9]{3}$'
                AND (
                        raw_job.raw_data #>> '{detail_evidence,status_code}'
                    )::integer BETWEEN 200 AND 399
            )
            OR
            -- Existing ATS-backed exact-detail authority (migration 093).
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
                AND NULLIF(btrim(raw_job.source_url), '')
                    = NULLIF(btrim(observation.source_url), '')
                AND coalesce(
                        raw_job.raw_data #>> '{detail_evidence,status_code}',
                        ''
                    ) ~ '^[0-9]{3}$'
                AND (
                        raw_job.raw_data #>> '{detail_evidence,status_code}'
                    )::integer BETWEEN 200 AND 399
            )
            OR
            -- Current recurring evidence from a reviewed Personio full inventory.
            -- The source-local raw row may predate the authority contract, so all
            -- freshness-critical proof is required on this exact observation.
            (
                observation.normalized_evidence IS NOT NULL
                AND observation.normalized_evidence #>> '{raw_evidence,source_type}'
                    = 'employer_origin_ats_backed_career_site'
                AND observation.normalized_evidence
                        #>> '{raw_evidence,ats_feed_authority,contract_version}'
                    = 'personio-recurring-feed-authority.v1'
                AND observation.normalized_evidence
                        #>> '{raw_evidence,ats_feed_authority,reviewed_binding_contract}'
                    = 'runtime_203_personio_target_authority_shadow_v1'
                AND observation.normalized_evidence
                        #>> '{raw_evidence,ats_feed_authority,provider}'
                    = 'personio'
                AND observation.normalized_evidence
                        #>> '{raw_evidence,ats_feed_authority,authority_validated}'
                    = 'true'
                AND observation.normalized_evidence
                        #>> '{raw_evidence,ats_feed_authority,employer_identity_bound}'
                    = 'true'
                AND observation.normalized_evidence
                        #>> '{raw_evidence,ats_feed_authority,feed_inventory_complete}'
                    = 'true'
                AND coalesce(
                        observation.normalized_evidence
                            #>> '{raw_evidence,ats_feed_authority,product_authority}',
                        'false'
                    ) = 'false'
                AND NULLIF(
                        btrim(
                            observation.normalized_evidence
                                #>> '{raw_evidence,ats_feed_authority,evidence_fingerprint}'
                        ),
                        ''
                    ) IS NOT NULL
                AND NULLIF(
                        btrim(
                            observation.normalized_evidence
                                #>> '{raw_evidence,ats_feed_authority,matched_company_name}'
                        ),
                        ''
                    ) IS NOT NULL
                AND NULLIF(
                        btrim(
                            observation.normalized_evidence
                                #>> '{raw_evidence,ats_feed_authority,target_key}'
                        ),
                        ''
                    ) IS NOT NULL
                AND observation.source_name
                    = 'personio:' || (
                        observation.normalized_evidence
                            #>> '{raw_evidence,ats_feed_authority,target_key}'
                      )
                AND observation.normalized_evidence
                        #>> '{raw_evidence,source_target,target_key}'
                    = observation.normalized_evidence
                        #>> '{raw_evidence,ats_feed_authority,target_key}'
                AND NULLIF(
                        btrim(
                            observation.normalized_evidence
                                #>> '{raw_evidence,job,source_url}'
                        ),
                        ''
                    ) = NULLIF(btrim(observation.source_url), '')
                AND NULLIF(
                        btrim(observation.normalized_evidence ->> 'source_url'),
                        ''
                    ) = NULLIF(btrim(observation.source_url), '')
                AND coalesce(
                        observation.normalized_evidence
                            #>> '{raw_evidence,ats_feed_authority,http_status_code}',
                        ''
                    ) ~ '^[0-9]{3}$'
                AND (
                        observation.normalized_evidence
                            #>> '{raw_evidence,ats_feed_authority,http_status_code}'
                    )::integer BETWEEN 200 AND 399
            )
          )
), authoritative_positive AS (
    SELECT DISTINCT ON (raw_job_id)
        raw_job_id,
        observed_at AS last_authoritative_positive_at,
        authority_coverage,
        authority_reason
    FROM authoritative_positive_candidates
    ORDER BY raw_job_id, observed_at DESC
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
                THEN authoritative.authority_coverage
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
                THEN authoritative.authority_reason
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

COMMENT ON VIEW gold_job_lifecycle_health IS
    'Current lifecycle truth from explicit health observations plus post-authority direct/ATS exact-detail observations and reviewed verified ATS full-feed recurring observations. Full-feed authority is read from the current job_observation normalized evidence; historical Bronze rows are not rewritten.';
