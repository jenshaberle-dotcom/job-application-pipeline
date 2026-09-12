"""Read-only F4A coverage diagnostic over the real Product database.

The report emits counts and status buckets only. Candidate Fact statements,
capability-tag values, provenance references and reviewer identities remain private.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.product_v1_contenders import classify_geography


CAPABILITY_EVIDENCE_CLASSES = (
    "professional_employment",
    "formal_education",
    "portfolio_implementation",
    "training_certification",
)


def _count(cur: psycopg.Cursor[dict], query: str, params: tuple[object, ...] = ()) -> int:
    cur.execute(query, params)
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("count query returned no row")
    return int(row["count"])


def main() -> int:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")

            current_jobs = _count(
                cur,
                "SELECT count(*) AS count FROM gold_current_job_opportunities",
            )
            assessments = _count(
                cur,
                """
                SELECT count(*) AS count
                FROM gold_current_job_opportunities current_job
                JOIN job_product_assessments assessment
                  ON assessment.silver_job_id = current_job.id
                """,
            )
            cur.execute(
                """
                SELECT profile_version, payload_sha256, status
                FROM candidate_fact_profiles
                WHERE profile_key = 'default'
                """
            )
            profile = cur.fetchone()
            profile_status = str(profile["status"]) if profile is not None else "absent"
            profile_hash = str(profile["payload_sha256"]) if profile is not None else ""

            approved_facts = _count(
                cur,
                """
                SELECT count(*) AS count
                FROM candidate_facts
                WHERE profile_key = 'default'
                  AND approval_status = 'approved'
                  AND (valid_from IS NULL OR valid_from <= current_date)
                  AND (valid_until IS NULL OR valid_until >= current_date)
                """,
            )
            capability_facts = _count(
                cur,
                """
                SELECT count(*) AS count
                FROM candidate_facts
                WHERE profile_key = 'default'
                  AND approval_status = 'approved'
                  AND evidence_class = ANY(%s)
                  AND (valid_from IS NULL OR valid_from <= current_date)
                  AND (valid_until IS NULL OR valid_until >= current_date)
                """,
                (list(CAPABILITY_EVIDENCE_CLASSES),),
            )
            preference_facts = _count(
                cur,
                """
                SELECT count(*) AS count
                FROM candidate_facts
                WHERE profile_key = 'default'
                  AND approval_status = 'approved'
                  AND category = 'preference'
                  AND (valid_from IS NULL OR valid_from <= current_date)
                  AND (valid_until IS NULL OR valid_until >= current_date)
                """,
            )
            boundary_facts = _count(
                cur,
                """
                SELECT count(*) AS count
                FROM candidate_facts
                WHERE profile_key = 'default'
                  AND approval_status = 'approved'
                  AND category = 'boundary'
                  AND (valid_from IS NULL OR valid_from <= current_date)
                  AND (valid_until IS NULL OR valid_until >= current_date)
                """,
            )

            active_capability_reviews = _count(
                cur,
                """
                SELECT count(*) AS count
                FROM product_v1_capability_fit_reviews review
                JOIN gold_current_job_opportunities current_job
                  ON current_job.id = review.silver_job_id
                WHERE review.status = 'active'
                """,
            )
            exact_capability_reviews = _count(
                cur,
                """
                SELECT count(*) AS count
                FROM product_v1_capability_fit_reviews review
                JOIN gold_current_job_opportunities current_job
                  ON current_job.id = review.silver_job_id
                JOIN job_product_assessments assessment
                  ON assessment.silver_job_id = review.silver_job_id
                WHERE review.status = 'active'
                  AND review.candidate_profile_sha256 = %s
                  AND review.assessment_updated_at = assessment.updated_at
                  AND review.assessment_detail_sha256 = coalesce(
                        assessment.ranking_factors ->> 'detail_description_sha256',
                        ''
                  )
                  AND jsonb_array_length(review.referenced_fact_keys) > 0
                  AND NOT EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements_text(review.referenced_fact_keys) wanted(fact_key)
                        LEFT JOIN candidate_facts fact
                          ON fact.profile_key = 'default'
                         AND fact.fact_key = wanted.fact_key
                         AND fact.approval_status = 'approved'
                         AND fact.evidence_class = ANY(%s)
                         AND (fact.valid_from IS NULL OR fact.valid_from <= current_date)
                         AND (fact.valid_until IS NULL OR fact.valid_until >= current_date)
                        WHERE fact.fact_key IS NULL
                  )
                """,
                (profile_hash, list(CAPABILITY_EVIDENCE_CLASSES)),
            ) if profile_status == "approved" else 0

            cur.execute(
                """
                SELECT coalesce(hard_filter.hard_filter_status, 'unknown') AS status,
                       count(*) AS count
                FROM gold_current_job_opportunities current_job
                LEFT JOIN gold_product_v1_hard_filter_evaluation hard_filter
                  ON hard_filter.silver_job_id = current_job.id
                GROUP BY coalesce(hard_filter.hard_filter_status, 'unknown')
                ORDER BY status
                """
            )
            hard_filter_counts = {
                str(row["status"]): int(row["count"]) for row in cur.fetchall()
            }

            cur.execute(
                """
                SELECT current_job.id AS silver_job_id,
                       current_job.city,
                       current_job.country,
                       assessment.work_model,
                       assessment.commute_minutes
                FROM gold_current_job_opportunities current_job
                LEFT JOIN job_product_assessments assessment
                  ON assessment.silver_job_id = current_job.id
                ORDER BY current_job.id
                """
            )
            geography = Counter(
                classify_geography(dict(row)).bucket for row in cur.fetchall()
            )

            cur.execute(
                """
                SELECT
                    count(*) FILTER (
                        WHERE assessment.requirements_seniority <> 'unknown'
                          AND assessment.seniority_evidence_status = 'observed'
                    ) AS requirements_seniority_observed,
                    count(*) FILTER (
                        WHERE assessment.work_model <> 'unknown'
                    ) AS work_model_observed,
                    count(*) FILTER (
                        WHERE assessment.commute_minutes IS NOT NULL
                    ) AS commute_observed,
                    count(*) FILTER (
                        WHERE assessment.employment_evidence_status = 'observed'
                    ) AS employment_observed,
                    count(*) FILTER (
                        WHERE assessment.language_evidence_status = 'observed'
                    ) AS language_observed,
                    count(*) FILTER (
                        WHERE assessment.weekly_hours_evidence_status = 'observed'
                    ) AS weekly_hours_observed
                FROM gold_current_job_opportunities current_job
                LEFT JOIN job_product_assessments assessment
                  ON assessment.silver_job_id = current_job.id
                """
            )
            evidence = cur.fetchone() or {}

        conn.rollback()

    print("=== F4A PROFILE FIT DIAGNOSTIC ===")
    print(f"CURRENT_CANONICAL_JOBS={current_jobs}")
    print(f"ASSESSMENT_ROWS={assessments}")
    print(f"CANDIDATE_PROFILE_STATUS={profile_status}")
    print(f"APPROVED_FACTS={approved_facts}")
    print(f"CAPABILITY_FACTS={capability_facts}")
    print(f"PREFERENCE_FACTS={preference_facts}")
    print(f"BOUNDARY_FACTS={boundary_facts}")
    print(f"ACTIVE_CAPABILITY_REVIEWS={active_capability_reviews}")
    print(f"EXACT_CURRENT_CAPABILITY_REVIEWS={exact_capability_reviews}")
    print("HARD_FILTER=" + ",".join(f"{key}:{value}" for key, value in sorted(hard_filter_counts.items())))
    print("GEOGRAPHY=" + ",".join(f"{key}:{value}" for key, value in sorted(geography.items())))
    for key in (
        "requirements_seniority_observed",
        "work_model_observed",
        "commute_observed",
        "employment_observed",
        "language_observed",
        "weekly_hours_observed",
    ):
        print(f"{key.upper()}={int(evidence.get(key) or 0)}")
    print("CANDIDATE_STATEMENTS_EMITTED=0")
    print("CAPABILITY_TAG_VALUES_EMITTED=0")
    print("PROVENANCE_REFERENCES_EMITTED=0")
    print("DATABASE_WRITES=0")
    print("F4A_PROFILE_FIT_DIAGNOSTIC=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
