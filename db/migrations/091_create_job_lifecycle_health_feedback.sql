-- JOB-LIFECYCLE-HEALTH-001
-- Separate historical Bronze/Silver memory from current vacancy truth.
--
-- This migration introduces explicit source-aware health observations and a
-- deterministic lifecycle projection. It intentionally does not invent a
-- freshness TTL, crawl historical jobs, activate sources, call providers or
-- mutate ranking/application state.

CREATE TABLE IF NOT EXISTS job_health_observations (
    id BIGSERIAL PRIMARY KEY,
    raw_job_id BIGINT NOT NULL REFERENCES raw_jobs(id),
    ingestion_run_id BIGINT REFERENCES ingestion_runs(id),
    source_name TEXT NOT NULL,
    external_job_id TEXT,
    source_url TEXT,
    outcome TEXT NOT NULL,
    coverage TEXT NOT NULL,
    evidence_reason TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    observed_by TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_job_health_outcome CHECK (
        outcome IN ('seen_active', 'not_seen', 'closed', 'unverifiable')
    ),
    CONSTRAINT chk_job_health_coverage CHECK (
        coverage IN (
            'exact_detail',
            'complete_inventory',
            'partial_listing',
            'unknown'
        )
    ),
    CONSTRAINT chk_job_health_closed_requires_exact_detail CHECK (
        outcome <> 'closed' OR coverage = 'exact_detail'
    ),
    CONSTRAINT chk_job_health_source_name CHECK (btrim(source_name) <> ''),
    CONSTRAINT chk_job_health_reason CHECK (btrim(evidence_reason) <> ''),
    CONSTRAINT chk_job_health_observer CHECK (btrim(observed_by) <> '')
);

CREATE INDEX IF NOT EXISTS idx_job_health_observations_raw_latest
ON job_health_observations (raw_job_id, observed_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_job_health_observations_source_external
ON job_health_observations (source_name, external_job_id, observed_at DESC);

COMMENT ON TABLE job_health_observations IS
'Append-only source-aware vacancy health evidence. Absence is not closure unless coverage is authoritative.';

CREATE OR REPLACE VIEW gold_job_lifecycle_health AS
WITH historical_positive AS (
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
        sj.id AS silver_job_id,
        sj.raw_job_id,
        sj.source_name,
        sj.external_job_id,
        p.last_positive_observed_at,
        CASE
            WHEN h.raw_job_id IS NULL THEN NULL
            WHEN p.last_positive_observed_at > h.observed_at
                THEN p.last_positive_observed_at
            ELSE h.observed_at
        END AS last_health_checked_at,
        h.outcome AS latest_health_outcome,
        h.coverage AS latest_health_coverage,
        CASE
            WHEN h.raw_job_id IS NULL
                THEN 'stale_needs_refresh'
            WHEN p.last_positive_observed_at > h.observed_at
                THEN 'active_confirmed'
            WHEN h.outcome = 'seen_active'
                THEN 'active_confirmed'
            WHEN h.outcome = 'closed'
             AND h.coverage = 'exact_detail'
                THEN 'inactive_confirmed'
            WHEN h.outcome = 'not_seen'
             AND h.coverage = 'complete_inventory'
                THEN 'inactive_confirmed'
            ELSE 'unverifiable'
        END AS lifecycle_status,
        CASE
            WHEN h.raw_job_id IS NULL
                THEN 'no_explicit_health_baseline'
            WHEN p.last_positive_observed_at > h.observed_at
                THEN 'source_local_job_reobserved_after_health_check'
            ELSE h.evidence_reason
        END AS lifecycle_evidence_reason,
        h.observed_by AS latest_health_observed_by
    FROM silver_jobs sj
    LEFT JOIN last_positive p
      ON p.raw_job_id = sj.raw_job_id
    LEFT JOIN latest_health h
      ON h.raw_job_id = sj.raw_job_id
)
SELECT *
FROM resolved;

CREATE OR REPLACE VIEW gold_current_job_opportunities AS
SELECT
    sj.*,
    lifecycle.lifecycle_status,
    lifecycle.last_positive_observed_at,
    lifecycle.last_health_checked_at,
    lifecycle.lifecycle_evidence_reason,
    lifecycle.latest_health_outcome,
    lifecycle.latest_health_coverage
FROM silver_jobs sj
JOIN gold_job_lifecycle_health lifecycle
  ON lifecycle.silver_job_id = sj.id
WHERE lifecycle.lifecycle_status = 'active_confirmed';

-- Preserve every existing Product V1 readiness column in exact order and type.
-- The existing activity_status name now exposes lifecycle-effective activity;
-- the old assessment value remains visible as an appended diagnostic field.
CREATE OR REPLACE VIEW gold_product_v1_job_readiness AS
WITH approved_policy AS (
    SELECT *
    FROM product_v1_ranking_policy
    WHERE policy_key = 'default'
), scored AS (
    SELECT
        sj.id AS silver_job_id,
        sj.title,
        sj.company_name,
        sj.city,
        sj.country,
        sj.publication_date,
        sj.source_name,
        sj.source_url,
        sj.canonical_source_type,
        a.origin_validation_status,
        CASE coalesce(lifecycle.lifecycle_status, 'stale_needs_refresh')
            WHEN 'active_confirmed' THEN 'active'
            WHEN 'inactive_confirmed' THEN 'inactive'
            ELSE 'unknown'
        END AS activity_status,
        coalesce(h.hard_filter_status, 'unknown') AS hard_filter_status,
        a.profile_direction_score,
        a.data_focus_score,
        a.reliability_focus_score,
        a.evidence_quality_score,
        CASE
            WHEN p.status = 'approved'
             AND a.profile_direction_score IS NOT NULL
             AND a.data_focus_score IS NOT NULL
             AND a.reliability_focus_score IS NOT NULL
             AND a.evidence_quality_score IS NOT NULL
            THEN round(
                (
                    a.profile_direction_score
                        * (p.ranking_weights ->> 'profile_direction')::numeric
                    + a.reliability_focus_score
                        * (p.ranking_weights ->> 'reliability_focus')::numeric
                    + a.data_focus_score
                        * (p.ranking_weights ->> 'data_focus')::numeric
                    + a.evidence_quality_score
                        * (p.ranking_weights ->> 'evidence_quality')::numeric
                ) / nullif(
                    (p.ranking_weights ->> 'profile_direction')::numeric
                    + (p.ranking_weights ->> 'reliability_focus')::numeric
                    + (p.ranking_weights ->> 'data_focus')::numeric
                    + (p.ranking_weights ->> 'evidence_quality')::numeric,
                    0
                ),
                2
            )
            ELSE NULL
        END AS overall_quality_score,
        a.work_model,
        a.commute_minutes,
        a.public_transport_quality,
        a.explanations,
        a.uncertainties,
        p.policy_key,
        p.policy_version,
        h.hard_filter_reasons,
        h.salary_signal,
        p.status AS ranking_policy_status,
        coalesce(
            lifecycle.lifecycle_status,
            'stale_needs_refresh'
        ) AS lifecycle_status,
        lifecycle.last_positive_observed_at,
        lifecycle.last_health_checked_at,
        coalesce(
            lifecycle.lifecycle_evidence_reason,
            'no_explicit_health_baseline'
        ) AS lifecycle_evidence_reason,
        lifecycle.latest_health_outcome,
        lifecycle.latest_health_coverage,
        a.activity_status AS assessment_activity_status
    FROM silver_jobs sj
    LEFT JOIN job_product_assessments a
      ON a.silver_job_id = sj.id
    LEFT JOIN gold_product_v1_hard_filter_evaluation h
      ON h.silver_job_id = sj.id
    LEFT JOIN approved_policy p
      ON p.policy_key = 'default'
    LEFT JOIN gold_job_lifecycle_health lifecycle
      ON lifecycle.silver_job_id = sj.id
)
SELECT
    silver_job_id,
    title,
    company_name,
    city,
    country,
    publication_date,
    source_name,
    source_url,
    canonical_source_type,
    origin_validation_status,
    activity_status,
    hard_filter_status,
    profile_direction_score,
    data_focus_score,
    reliability_focus_score,
    evidence_quality_score,
    overall_quality_score,
    work_model,
    commute_minutes,
    public_transport_quality,
    explanations,
    uncertainties,
    policy_key,
    policy_version,
    CASE
        WHEN origin_validation_status IS NULL THEN 'assessment_required'
        WHEN origin_validation_status = 'rejected' THEN 'blocked_origin'
        WHEN origin_validation_status = 'pending'
            THEN 'origin_validation_required'
        WHEN activity_status = 'inactive' THEN 'blocked_inactive'
        WHEN activity_status = 'unknown'
            THEN 'activity_evidence_required'
        WHEN hard_filter_status = 'failed' THEN 'blocked_hard_filter'
        WHEN hard_filter_status = 'unknown'
            THEN 'hard_filter_evidence_required'
        WHEN overall_quality_score IS NULL THEN 'assessment_required'
        WHEN ranking_policy_status <> 'approved'
            THEN 'ranking_policy_required'
        ELSE 'rankable'
    END AS product_readiness_status,
    hard_filter_reasons,
    salary_signal,
    ranking_policy_status,
    lifecycle_status,
    last_positive_observed_at,
    last_health_checked_at,
    lifecycle_evidence_reason,
    latest_health_outcome,
    latest_health_coverage,
    assessment_activity_status
FROM scored;
