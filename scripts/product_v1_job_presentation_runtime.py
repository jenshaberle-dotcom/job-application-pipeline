"""Read-only runtime enrichment for Product V1 operator job presentation.

This layer has no ranking or application authority. It binds Product V1 rows to
persisted observation evidence to improve display semantics and defines the normal
operator review scope as current employer-origin vacancies only. Historical Product
memory and market-sensor rows remain separately auditable.
"""
from __future__ import annotations

from typing import Mapping

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig
from src.search_intelligence.product_v1_job_presentation import decorate_job_for_operator


EMPLOYER_ORIGIN_SOURCE_TYPES = frozenset(
    {
        "employer_origin_career_site",
        "employer_origin_ats_backed_career_site",
    }
)
EMPLOYER_ORIGIN_SOURCE_PREFIXES = (
    "generic_origin:",
    "personio:",
    "successfactors:",
    "greenhouse:",
    "workday:",
    "enercity:",
    "hdi:",
    "finanz_informatik:",
)
MARKET_SENSOR_SOURCE_FAMILIES = frozenset(
    {
        "bundesagentur_fuer_arbeit",
        "stepstone",
        "gute_jobs",
        "gute-jobs",
        "indeed",
        "linkedin",
    }
)


def _silver_job_ids(payload: Mapping[str, object]) -> list[int]:
    raw = payload.get("job_readiness")
    if not isinstance(raw, list):
        return []
    result: set[int] = set()
    for item in raw:
        if not isinstance(item, Mapping) or item.get("silver_job_id") is None:
            continue
        try:
            result.add(int(item["silver_job_id"]))
        except (TypeError, ValueError):
            continue
    return sorted(result)


def load_latest_observation_evidence(
    silver_job_ids: list[int],
) -> dict[int, object]:
    """Load latest normalized evidence plus the first persisted JAP sighting."""

    if not silver_job_ids:
        return {}
    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(),
        row_factory=dict_row,
    ) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    SELECT
                        silver.id AS silver_job_id,
                        latest.normalized_evidence,
                        first_seen.first_jap_observed_at
                    FROM silver_jobs silver
                    LEFT JOIN LATERAL (
                        SELECT observation.normalized_evidence
                        FROM job_observations observation
                        WHERE observation.raw_job_id = silver.raw_job_id
                        ORDER BY observation.observed_at DESC, observation.id DESC
                        LIMIT 1
                    ) latest ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT min(observation.observed_at) AS first_jap_observed_at
                        FROM job_observations observation
                        WHERE observation.raw_job_id = silver.raw_job_id
                          AND observation.is_seen = TRUE
                    ) first_seen ON TRUE
                    WHERE silver.id = ANY(%s)
                    ORDER BY silver.id
                    """,
                    (silver_job_ids,),
                )
                rows = tuple(cur.fetchall())
        conn.rollback()
    return {
        int(row["silver_job_id"]): {
            "normalized_evidence": row.get("normalized_evidence"),
            "first_jap_observed_at": row.get("first_jap_observed_at"),
        }
        for row in rows
        if row.get("silver_job_id") is not None
    }


def is_current_product_job(row: Mapping[str, object]) -> bool:
    return (
        str(row.get("lifecycle_status") or "").replace("_", " ").casefold()
        == "active confirmed"
    )


def is_employer_origin_review_source(row: Mapping[str, object]) -> bool:
    source_name = str(row.get("source_name") or "").strip().casefold()
    source_family = source_name.split(":", 1)[0]
    if source_family in MARKET_SENSOR_SOURCE_FAMILIES:
        return False
    if str(row.get("canonical_source_type") or "") in EMPLOYER_ORIGIN_SOURCE_TYPES:
        return True
    return any(source_name.startswith(prefix) for prefix in EMPLOYER_ORIGIN_SOURCE_PREFIXES)


def _observation_parts(value: object) -> tuple[object, object]:
    """Accept both the new wrapper and the legacy direct-evidence test shape."""

    if isinstance(value, Mapping) and (
        "normalized_evidence" in value or "first_jap_observed_at" in value
    ):
        return value.get("normalized_evidence"), value.get("first_jap_observed_at")
    return value, None


def _decorate_collection(
    raw_collection: object,
    *,
    evidence_by_job: Mapping[int, object],
) -> list[object]:
    if not isinstance(raw_collection, list):
        return []
    decorated: list[object] = []
    for item in raw_collection:
        if not isinstance(item, Mapping):
            decorated.append(item)
            continue
        raw_id = item.get("silver_job_id")
        try:
            silver_job_id = int(raw_id) if raw_id is not None else None
        except (TypeError, ValueError):
            silver_job_id = None
        evidence = evidence_by_job.get(silver_job_id) if silver_job_id is not None else None
        normalized_evidence, first_observed = _observation_parts(evidence)
        projected = decorate_job_for_operator(
            item,
            normalized_observation_evidence=normalized_evidence,
        )
        projected["first_jap_observed_at"] = first_observed
        decorated.append(projected)
    return decorated


def enrich_product_payload_for_operator(
    payload: Mapping[str, object],
    *,
    observation_evidence: Mapping[int, object] | None = None,
) -> dict[str, object]:
    """Build current Employer-Origin review truth without mutating Product authority.

    Normal `job_readiness` contains only lifecycle-current employer-origin vacancies
    that are geography-review eligible. Sensor-derived Product memory and historical
    origin jobs remain separately auditable. Top-5 membership is never filtered or
    rewritten here.
    """

    result = dict(payload)
    evidence_by_job = (
        dict(observation_evidence)
        if observation_evidence is not None
        else load_latest_observation_evidence(_silver_job_ids(payload))
    )

    decorated_readiness = _decorate_collection(
        result.get("job_readiness"),
        evidence_by_job=evidence_by_job,
    )
    review_scope: list[object] = []
    out_of_profile: list[object] = []
    historical_jobs: list[object] = []
    discovery_source_jobs: list[object] = []
    for item in decorated_readiness:
        if not isinstance(item, Mapping):
            continue
        if not is_employer_origin_review_source(item):
            discovery_source_jobs.append(item)
            continue
        if not is_current_product_job(item):
            historical_jobs.append(item)
            continue
        if item.get("profile_geography_eligible") is False:
            out_of_profile.append(item)
            continue
        review_scope.append(item)

    result["job_readiness"] = review_scope
    result["out_of_profile_jobs"] = out_of_profile
    result["historical_jobs"] = historical_jobs
    result["discovery_source_jobs"] = discovery_source_jobs
    result["top_jobs"] = _decorate_collection(
        result.get("top_jobs"),
        evidence_by_job=evidence_by_job,
    )

    summary = dict(result.get("summary") or {})
    summary["review_scope_job_count"] = len(review_scope)
    summary["review_scope_current_active_job_count"] = len(review_scope)
    summary["out_of_profile_job_count"] = len(out_of_profile)
    summary["historical_review_excluded_job_count"] = len(historical_jobs)
    summary["discovery_source_review_excluded_job_count"] = len(discovery_source_jobs)
    result["summary"] = summary

    boundaries = dict(result.get("boundaries") or {})
    boundaries.update(
        {
            "job_presentation_enrichment_is_not_ranking_authority": True,
            "job_presentation_enrichment_is_not_application_authority": True,
            "qualitative_schedule_never_infers_numeric_hours": True,
            "review_geography_does_not_rewrite_product_truth": True,
            "out_of_profile_jobs_remain_auditable": True,
            "historical_jobs_remain_auditable": True,
            "market_sensor_jobs_remain_discovery_evidence_only": True,
            "normal_review_scope_requires_current_employer_origin": True,
            "first_jap_observed_is_observation_history_not_source_publish_time": True,
            "top5_membership_not_filtered_by_presentation": True,
        }
    )
    result["boundaries"] = boundaries
    return result


__all__ = [
    "enrich_product_payload_for_operator",
    "is_current_product_job",
    "is_employer_origin_review_source",
    "load_latest_observation_evidence",
]
