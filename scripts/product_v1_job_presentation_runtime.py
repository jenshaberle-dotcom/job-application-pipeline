"""Read-only runtime enrichment for Product V1 operator job presentation.

This layer has no ranking or application authority. It binds current Product V1 rows to
the latest persisted normalized observation only to improve display semantics such as
reviewed employer brand, legal entity, qualitative schedule and review geography.
"""
from __future__ import annotations

from typing import Mapping

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig
from src.search_intelligence.product_v1_job_presentation import decorate_job_for_operator


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
                        latest.normalized_evidence
                    FROM silver_jobs silver
                    LEFT JOIN LATERAL (
                        SELECT observation.normalized_evidence
                        FROM job_observations observation
                        WHERE observation.raw_job_id = silver.raw_job_id
                        ORDER BY observation.observed_at DESC, observation.id DESC
                        LIMIT 1
                    ) latest ON TRUE
                    WHERE silver.id = ANY(%s)
                    ORDER BY silver.id
                    """,
                    (silver_job_ids,),
                )
                rows = tuple(cur.fetchall())
        conn.rollback()
    return {
        int(row["silver_job_id"]): row.get("normalized_evidence")
        for row in rows
        if row.get("silver_job_id") is not None
    }


def enrich_product_payload_for_operator(
    payload: Mapping[str, object],
    *,
    observation_evidence: Mapping[int, object] | None = None,
) -> dict[str, object]:
    """Decorate job collections without changing membership, score or Product authority."""

    result = dict(payload)
    evidence_by_job = (
        dict(observation_evidence)
        if observation_evidence is not None
        else load_latest_observation_evidence(_silver_job_ids(payload))
    )

    for collection_name in ("job_readiness", "top_jobs"):
        raw_collection = result.get(collection_name)
        if not isinstance(raw_collection, list):
            continue
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
            decorated.append(
                decorate_job_for_operator(
                    item,
                    normalized_observation_evidence=(
                        evidence_by_job.get(silver_job_id)
                        if silver_job_id is not None
                        else None
                    ),
                )
            )
        result[collection_name] = decorated

    boundaries = dict(result.get("boundaries") or {})
    boundaries.update(
        {
            "job_presentation_enrichment_is_not_ranking_authority": True,
            "job_presentation_enrichment_is_not_application_authority": True,
            "qualitative_schedule_never_infers_numeric_hours": True,
            "review_geography_does_not_rewrite_product_truth": True,
        }
    )
    result["boundaries"] = boundaries
    return result


__all__ = [
    "enrich_product_payload_for_operator",
    "load_latest_observation_evidence",
]
