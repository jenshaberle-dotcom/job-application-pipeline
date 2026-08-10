"""Persistence adapter for append-only job lifecycle health observations."""
from __future__ import annotations

import json
from collections.abc import Mapping

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.job_lifecycle import (
    JobHealthObservation,
    validate_job_health_observation,
)


class JobHealthObservationRepository:
    """Record source-sensor evidence without deciding Product V1 ranking truth."""

    def __init__(self, connection_config: Mapping[str, object] | None = None) -> None:
        self.connection_config = dict(connection_config or get_database_config())

    def record(
        self,
        observation: JobHealthObservation,
        *,
        ingestion_run_id: int | None = None,
    ) -> int:
        validated = validate_job_health_observation(observation)

        with psycopg.connect(
            **self.connection_config,
            row_factory=dict_row,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        source_name,
                        external_job_id
                    FROM raw_jobs
                    WHERE id = %s
                    FOR SHARE
                    """,
                    (validated.raw_job_id,),
                )
                raw_job = cur.fetchone()
                if raw_job is None:
                    raise ValueError(
                        f"raw job does not exist: {validated.raw_job_id}"
                    )
                if str(raw_job["source_name"]) != validated.source_name:
                    raise ValueError("raw job source_name drift detected")
                if (
                    validated.external_job_id is not None
                    and raw_job["external_job_id"] != validated.external_job_id
                ):
                    raise ValueError("raw job external_job_id drift detected")

                cur.execute(
                    """
                    INSERT INTO job_health_observations (
                        raw_job_id,
                        ingestion_run_id,
                        source_name,
                        external_job_id,
                        source_url,
                        outcome,
                        coverage,
                        evidence_reason,
                        evidence,
                        observed_by,
                        observed_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s::jsonb, %s, %s
                    )
                    RETURNING id
                    """,
                    (
                        validated.raw_job_id,
                        ingestion_run_id,
                        validated.source_name,
                        validated.external_job_id,
                        validated.source_url,
                        validated.outcome,
                        validated.coverage,
                        validated.evidence_reason,
                        json.dumps(dict(validated.evidence), ensure_ascii=False),
                        validated.observed_by,
                        validated.observed_at,
                    ),
                )
                inserted = cur.fetchone()
                if inserted is None:
                    raise RuntimeError("health observation insert returned no id")
                return int(inserted["id"])
