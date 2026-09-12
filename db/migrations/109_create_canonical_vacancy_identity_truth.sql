-- F3-VACANCY-IDENTITY-001
--
-- Move safe vacancy identity out of presentation-only repair and into Gold truth.
-- Historical Bronze/Silver rows are preserved. This migration does not delete,
-- rewrite or merge source records; it projects one current canonical representative
-- while retaining every membership row for audit.
--
-- Identity order:
--   1. same Origin host + strong labelled/schema vacancy identifier;
--   2. same exact page-declared canonical Origin URL;
--   3. tightly bounded same-run detail equivalence for generic Origin aliases;
--   4. exact observed Origin URL;
--   5. isolated Silver identity.
--
-- The bounded equivalence is deliberately stronger than URL path normalization.
-- A locale-neutral path can participate only when two or more current rows from the
-- same generic source and same ingestion run have exactly equal structured detail
-- evidence and no conflicting strong identifier. There is no employer allowlist,
-- title/company fuzzy match, or global locale-segment rewrite authority.

CREATE OR REPLACE FUNCTION jap_origin_host(value text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN value IS NULL OR btrim(value) = '' THEN NULL
        WHEN btrim(value) !~* '^https?://' THEN NULL
        ELSE NULLIF(
            lower(
                regexp_replace(
                    split_part(
                        split_part(btrim(value), '://', 2),
                        '/',
                        1
                    ),
                    '^www\\.',
                    '',
                    'i'
                )
            ),
            ''
        )
    END
$$;

CREATE OR REPLACE FUNCTION jap_exact_origin_url(value text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN value IS NULL OR btrim(value) = '' THEN NULL
        WHEN btrim(value) !~* '^https?://' THEN NULL
        ELSE regexp_replace(btrim(value), '/+$', '')
    END
$$;

CREATE OR REPLACE FUNCTION jap_locale_neutral_origin_path(value text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN value IS NULL OR btrim(value) = '' THEN NULL
        WHEN btrim(value) !~* '^https?://' THEN NULL
        ELSE regexp_replace(
            split_part(
                regexp_replace(btrim(value), '^https?://[^/]+', '', 'i'),
                '?',
                1
            ),
            '^/(de|en|fr|es|it|nl|pl)(/|$)',
            '/',
            'i'
        )
    END
$$;

CREATE OR REPLACE VIEW gold_vacancy_identity AS
WITH latest_seen AS (
    SELECT DISTINCT ON (observation.raw_job_id)
        observation.raw_job_id,
        observation.ingestion_run_id,
        observation.observed_at,
        observation.source_url AS observation_source_url,
        observation.normalized_evidence
    FROM job_observations observation
    WHERE observation.raw_job_id IS NOT NULL
      AND observation.is_seen = TRUE
    ORDER BY
        observation.raw_job_id,
        observation.observed_at DESC,
        observation.id DESC
), evidence AS (
    SELECT
        silver.id AS silver_job_id,
        silver.raw_job_id,
        silver.source_name,
        silver.source_url,
        lifecycle.lifecycle_status,
        latest.ingestion_run_id,
        latest.observed_at AS latest_seen_at,
        coalesce(latest.observation_source_url, silver.source_url) AS observed_origin_url,
        NULLIF(
            btrim(
                latest.normalized_evidence
                    #>> '{raw_evidence,job,metadata,canonical_origin_url}'
            ),
            ''
        ) AS canonical_origin_url,
        CASE
            WHEN lower(coalesce(
                    latest.normalized_evidence
                        #>> '{raw_evidence,job,metadata,identifier_evidence_kind}',
                    ''
                 )) IN ('schema_org', 'explicit_label')
             AND NULLIF(
                    btrim(
                        latest.normalized_evidence
                            #>> '{raw_evidence,job,metadata,structured_identifier}'
                    ),
                    ''
                 ) IS NOT NULL
             AND btrim(
                    latest.normalized_evidence
                        #>> '{raw_evidence,job,metadata,structured_identifier}'
                 ) ~ '[0-9]'
             AND btrim(
                    latest.normalized_evidence
                        #>> '{raw_evidence,job,metadata,structured_identifier}'
                 ) ~ '^[A-Za-z0-9._/-]+$'
            THEN lower(
                btrim(
                    regexp_replace(
                        latest.normalized_evidence
                            #>> '{raw_evidence,job,metadata,structured_identifier}',
                        '\\s+',
                        '',
                        'g'
                    ),
                    '.:,;()[]{}'
                )
            )
            ELSE NULL
        END AS strong_identifier,
        lower(coalesce(
            latest.normalized_evidence
                #>> '{raw_evidence,job,metadata,identifier_evidence_kind}',
            ''
        )) AS identifier_evidence_kind,
        jap_origin_host(
            coalesce(
                NULLIF(
                    btrim(
                        latest.normalized_evidence
                            #>> '{raw_evidence,job,metadata,canonical_origin_url}'
                    ),
                    ''
                ),
                latest.observation_source_url,
                silver.source_url
            )
        ) AS origin_host,
        jap_exact_origin_url(
            NULLIF(
                btrim(
                    latest.normalized_evidence
                        #>> '{raw_evidence,job,metadata,canonical_origin_url}'
                ),
                ''
            )
        ) AS exact_canonical_origin_url,
        jap_exact_origin_url(
            coalesce(latest.observation_source_url, silver.source_url)
        ) AS exact_observed_origin_url,
        jap_locale_neutral_origin_path(
            coalesce(latest.observation_source_url, silver.source_url)
        ) AS locale_neutral_origin_path,
        CASE
            WHEN NULLIF(
                    btrim(
                        latest.normalized_evidence
                            #>> '{raw_evidence,job,title}'
                    ),
                    ''
                 ) IS NOT NULL
             AND NULLIF(
                    btrim(
                        latest.normalized_evidence
                            #>> '{raw_evidence,job,description}'
                    ),
                    ''
                 ) IS NOT NULL
            THEN md5(
                jsonb_build_object(
                    'title', regexp_replace(
                        coalesce(
                            latest.normalized_evidence #>> '{raw_evidence,job,title}',
                            ''
                        ),
                        '\\s+', ' ', 'g'
                    ),
                    'company_name', regexp_replace(
                        coalesce(
                            latest.normalized_evidence #>> '{raw_evidence,job,company_name}',
                            ''
                        ),
                        '\\s+', ' ', 'g'
                    ),
                    'description', regexp_replace(
                        coalesce(
                            latest.normalized_evidence #>> '{raw_evidence,job,description}',
                            ''
                        ),
                        '\\s+', ' ', 'g'
                    ),
                    'location', regexp_replace(
                        coalesce(
                            latest.normalized_evidence #>> '{raw_evidence,job,location}',
                            ''
                        ),
                        '\\s+', ' ', 'g'
                    ),
                    'locations', latest.normalized_evidence
                        #> '{raw_evidence,job,locations}',
                    'applicant_locations', latest.normalized_evidence
                        #> '{raw_evidence,job,applicant_locations}',
                    'skills', latest.normalized_evidence
                        #> '{raw_evidence,job,skills}',
                    'workplace_type', regexp_replace(
                        coalesce(
                            latest.normalized_evidence
                                #>> '{raw_evidence,job,metadata,workplace_type}',
                            ''
                        ),
                        '\\s+', ' ', 'g'
                    ),
                    'employment_types', latest.normalized_evidence
                        #> '{raw_evidence,job,metadata,employment_types}',
                    'date_posted', regexp_replace(
                        coalesce(
                            latest.normalized_evidence
                                #>> '{raw_evidence,job,metadata,date_posted}',
                            ''
                        ),
                        '\\s+', ' ', 'g'
                    ),
                    'valid_through', regexp_replace(
                        coalesce(
                            latest.normalized_evidence
                                #>> '{raw_evidence,job,metadata,valid_through}',
                            ''
                        ),
                        '\\s+', ' ', 'g'
                    )
                )::text
            )
            ELSE NULL
        END AS semantic_evidence_fingerprint
    FROM silver_jobs silver
    LEFT JOIN latest_seen latest
      ON latest.raw_job_id = silver.raw_job_id
    LEFT JOIN gold_job_lifecycle_health lifecycle
      ON lifecycle.silver_job_id = silver.id
), canonical_counts AS (
    SELECT
        exact_canonical_origin_url,
        count(*) AS member_count
    FROM evidence
    WHERE exact_canonical_origin_url IS NOT NULL
    GROUP BY exact_canonical_origin_url
), bounded_stats AS (
    SELECT
        source_name,
        origin_host,
        ingestion_run_id,
        semantic_evidence_fingerprint,
        locale_neutral_origin_path,
        count(*) AS member_count,
        count(DISTINCT exact_observed_origin_url) AS distinct_origin_url_count,
        count(DISTINCT strong_identifier) AS distinct_strong_identifier_count,
        max(strong_identifier) AS single_strong_identifier
    FROM evidence
    WHERE lifecycle_status = 'active_confirmed'
      AND source_name LIKE 'generic_origin:%'
      AND origin_host IS NOT NULL
      AND ingestion_run_id IS NOT NULL
      AND semantic_evidence_fingerprint IS NOT NULL
      AND locale_neutral_origin_path IS NOT NULL
      AND exact_observed_origin_url IS NOT NULL
    GROUP BY
        source_name,
        origin_host,
        ingestion_run_id,
        semantic_evidence_fingerprint,
        locale_neutral_origin_path
    HAVING count(DISTINCT exact_observed_origin_url) > 1
       AND count(DISTINCT strong_identifier) <= 1
), resolved AS (
    SELECT
        evidence.*,
        bounded.member_count AS bounded_member_count,
        bounded.distinct_origin_url_count AS bounded_distinct_origin_url_count,
        CASE
            WHEN evidence.origin_host IS NOT NULL
             AND coalesce(
                    evidence.strong_identifier,
                    bounded.single_strong_identifier
                 ) IS NOT NULL
                THEN 'strong_origin_identifier'
            WHEN evidence.exact_canonical_origin_url IS NOT NULL
             AND coalesce(canonical.member_count, 0) > 1
                THEN 'exact_canonical_origin_url'
            WHEN bounded.member_count IS NOT NULL
                THEN 'bounded_same_run_detail_equivalence'
            WHEN evidence.exact_observed_origin_url IS NOT NULL
                THEN 'exact_observed_origin_url'
            ELSE 'isolated_silver_identity'
        END AS identity_kind,
        CASE
            WHEN evidence.origin_host IS NOT NULL
             AND coalesce(
                    evidence.strong_identifier,
                    bounded.single_strong_identifier
                 ) IS NOT NULL
                THEN 'origin-id|' || evidence.origin_host || '|'
                    || coalesce(
                        evidence.strong_identifier,
                        bounded.single_strong_identifier
                    )
            WHEN evidence.exact_canonical_origin_url IS NOT NULL
             AND coalesce(canonical.member_count, 0) > 1
                THEN 'canonical-url|' || evidence.exact_canonical_origin_url
            WHEN bounded.member_count IS NOT NULL
                THEN 'bounded|' || evidence.origin_host || '|'
                    || evidence.locale_neutral_origin_path || '|'
                    || evidence.semantic_evidence_fingerprint
            WHEN evidence.exact_observed_origin_url IS NOT NULL
                THEN 'origin-url|' || evidence.exact_observed_origin_url
            ELSE 'silver|' || evidence.silver_job_id::text
        END AS canonical_vacancy_key
    FROM evidence
    LEFT JOIN canonical_counts canonical
      ON canonical.exact_canonical_origin_url
       = evidence.exact_canonical_origin_url
    LEFT JOIN bounded_stats bounded
      ON bounded.source_name = evidence.source_name
     AND bounded.origin_host = evidence.origin_host
     AND bounded.ingestion_run_id = evidence.ingestion_run_id
     AND bounded.semantic_evidence_fingerprint
       = evidence.semantic_evidence_fingerprint
     AND bounded.locale_neutral_origin_path
       = evidence.locale_neutral_origin_path
), ranked AS (
    SELECT
        resolved.*,
        count(*) OVER (
            PARTITION BY canonical_vacancy_key
        ) AS identity_group_size,
        row_number() OVER (
            PARTITION BY canonical_vacancy_key
            ORDER BY
                CASE lifecycle_status
                    WHEN 'active_confirmed' THEN 0
                    WHEN 'unverifiable' THEN 1
                    WHEN 'stale_needs_refresh' THEN 2
                    WHEN 'inactive_confirmed' THEN 3
                    ELSE 4
                END,
                CASE identity_kind
                    WHEN 'strong_origin_identifier' THEN 0
                    WHEN 'exact_canonical_origin_url' THEN 1
                    WHEN 'bounded_same_run_detail_equivalence' THEN 2
                    WHEN 'exact_observed_origin_url' THEN 3
                    ELSE 4
                END,
                latest_seen_at DESC NULLS LAST,
                silver_job_id
        ) AS identity_rank
    FROM resolved
)
SELECT
    silver_job_id,
    raw_job_id,
    source_name,
    source_url,
    lifecycle_status,
    ingestion_run_id,
    latest_seen_at,
    observed_origin_url,
    canonical_origin_url,
    strong_identifier,
    NULLIF(identifier_evidence_kind, '') AS identifier_evidence_kind,
    origin_host,
    exact_canonical_origin_url,
    exact_observed_origin_url,
    locale_neutral_origin_path,
    semantic_evidence_fingerprint,
    identity_kind,
    canonical_vacancy_key,
    identity_group_size,
    identity_rank = 1 AS is_representative
FROM ranked;

COMMENT ON VIEW gold_vacancy_identity IS
'Provider-neutral Gold vacancy identity membership. Strong labelled/schema identity wins; bounded same-run detail equivalence may bridge locale aliases only under exact multi-signal evidence. All Silver members remain auditable.';

-- Current opportunities now consume canonical identity truth upstream instead of
-- relying on presentation-time duplicate suppression.
CREATE OR REPLACE VIEW gold_current_job_opportunities AS
SELECT
    silver.*,
    lifecycle.lifecycle_status,
    lifecycle.last_positive_observed_at,
    lifecycle.last_health_checked_at,
    lifecycle.lifecycle_evidence_reason,
    lifecycle.latest_health_outcome,
    lifecycle.latest_health_coverage
FROM silver_jobs silver
JOIN gold_job_lifecycle_health lifecycle
  ON lifecycle.silver_job_id = silver.id
JOIN gold_vacancy_identity identity
  ON identity.silver_job_id = silver.id
 AND identity.is_representative
WHERE lifecycle.lifecycle_status = 'active_confirmed';

-- Preserve the Product V1 readiness column contract while changing its cohort
-- authority from every Silver row to canonical representative vacancies.
CREATE OR REPLACE VIEW gold_product_v1_job_readiness AS
WITH approved_policy AS (
    SELECT *
    FROM product_v1_ranking_policy
    WHERE policy_key = 'default'
), scored AS (
    SELECT
        silver.id AS silver_job_id,
        silver.title,
        silver.company_name,
        silver.city,
        silver.country,
        silver.publication_date,
        silver.source_name,
        silver.source_url,
        silver.canonical_source_type,
        assessment.origin_validation_status,
        CASE coalesce(lifecycle.lifecycle_status, 'stale_needs_refresh')
            WHEN 'active_confirmed' THEN 'active'
            WHEN 'inactive_confirmed' THEN 'inactive'
            ELSE 'unknown'
        END AS activity_status,
        coalesce(hard_filter.hard_filter_status, 'unknown') AS hard_filter_status,
        assessment.profile_direction_score,
        assessment.data_focus_score,
        assessment.reliability_focus_score,
        assessment.evidence_quality_score,
        CASE
            WHEN policy.status = 'approved'
             AND assessment.profile_direction_score IS NOT NULL
             AND assessment.data_focus_score IS NOT NULL
             AND assessment.reliability_focus_score IS NOT NULL
             AND assessment.evidence_quality_score IS NOT NULL
            THEN round(
                (
                    assessment.profile_direction_score
                        * (policy.ranking_weights ->> 'profile_direction')::numeric
                    + assessment.reliability_focus_score
                        * (policy.ranking_weights ->> 'reliability_focus')::numeric
                    + assessment.data_focus_score
                        * (policy.ranking_weights ->> 'data_focus')::numeric
                    + assessment.evidence_quality_score
                        * (policy.ranking_weights ->> 'evidence_quality')::numeric
                ) / nullif(
                    (policy.ranking_weights ->> 'profile_direction')::numeric
                    + (policy.ranking_weights ->> 'reliability_focus')::numeric
                    + (policy.ranking_weights ->> 'data_focus')::numeric
                    + (policy.ranking_weights ->> 'evidence_quality')::numeric,
                    0
                ),
                2
            )
            ELSE NULL
        END AS overall_quality_score,
        assessment.work_model,
        assessment.commute_minutes,
        assessment.public_transport_quality,
        assessment.explanations,
        assessment.uncertainties,
        policy.policy_key,
        policy.policy_version,
        hard_filter.hard_filter_reasons,
        hard_filter.salary_signal,
        policy.status AS ranking_policy_status,
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
        assessment.activity_status AS assessment_activity_status
    FROM silver_jobs silver
    JOIN gold_vacancy_identity identity
      ON identity.silver_job_id = silver.id
     AND identity.is_representative
    LEFT JOIN job_product_assessments assessment
      ON assessment.silver_job_id = silver.id
    LEFT JOIN gold_product_v1_hard_filter_evaluation hard_filter
      ON hard_filter.silver_job_id = silver.id
    LEFT JOIN approved_policy policy
      ON policy.policy_key = 'default'
    LEFT JOIN gold_job_lifecycle_health lifecycle
      ON lifecycle.silver_job_id = silver.id
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

COMMENT ON VIEW gold_product_v1_job_readiness IS
'Canonical Product V1 readiness: one safe representative per Gold vacancy identity. Suppressed aliases remain auditable in silver_jobs and gold_vacancy_identity.';
