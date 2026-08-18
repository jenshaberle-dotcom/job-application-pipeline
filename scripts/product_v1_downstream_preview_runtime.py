"""Read-only DB/runtime loader for Product V1 downstream evidence preview."""

from __future__ import annotations

from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig
from src.search_intelligence.product_v1_downstream_preview import (
    DownstreamPreviewStop,
    build_product_v1_downstream_preview,
    fetch_public_https_detail_text,
)


_PREVIEW_JOB_SQL = """
SELECT
    readiness.*,
    assessment.employment_type,
    assessment.employment_evidence_status,
    assessment.required_languages,
    assessment.language_evidence_status,
    assessment.weekly_hours_min,
    assessment.weekly_hours_max,
    assessment.weekly_hours_evidence_status,
    assessment.title_seniority,
    assessment.requirements_seniority,
    assessment.seniority_evidence_status,
    assessment.capability_fit_status,
    assessment.capability_fit_evidence_status
FROM gold_product_v1_job_readiness readiness
LEFT JOIN job_product_assessments assessment
  ON assessment.silver_job_id = readiness.silver_job_id
WHERE readiness.silver_job_id = %s
"""


@dataclass(frozen=True)
class DownstreamEvidenceMaterialization:
    """One DB-authoritative Product V1 target plus its current bounded detail text."""

    row: dict[str, object]
    final_url: str
    fetched_title: str
    detail_text: str


def _load_preview_job(silver_job_id: int) -> dict[str, object]:
    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(),
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(_PREVIEW_JOB_SQL, (silver_job_id,))
            row = cur.fetchone()
    if row is None:
        raise DownstreamPreviewStop("Silver job was not found")
    return dict(row)


def load_downstream_evidence_materialization(
    silver_job_id: int,
) -> DownstreamEvidenceMaterialization:
    """Load one authoritative row and fetch its current public detail text.

    This is the shared read-only boundary for deterministic preview and bounded
    Product V1 AI-booster campaigns. It performs no provider/model call and no
    database/product write.
    """

    if silver_job_id <= 0:
        raise DownstreamPreviewStop("silver_job_id must be positive")
    row = _load_preview_job(silver_job_id)
    if str(row.get("canonical_source_type") or "") != "employer_origin":
        raise DownstreamPreviewStop("employer-origin source authority is required")
    if str(row.get("origin_validation_status") or "") != "validated":
        raise DownstreamPreviewStop("validated origin authority is required")
    if str(row.get("activity_status") or "") != "active":
        raise DownstreamPreviewStop("current active vacancy authority is required")

    source_url = str(row.get("source_url") or "")
    final_url, fetched_title, detail_text = fetch_public_https_detail_text(source_url)
    return DownstreamEvidenceMaterialization(
        row=row,
        final_url=final_url,
        fetched_title=fetched_title,
        detail_text=detail_text,
    )


def load_downstream_evidence_preview_payload(silver_job_id: int) -> dict[str, object]:
    """Load one authoritative row and return provider-free deterministic preview."""

    materialization = load_downstream_evidence_materialization(silver_job_id)
    return build_product_v1_downstream_preview(
        row=materialization.row,
        final_url=materialization.final_url,
        fetched_title=materialization.fetched_title,
        detail_text=materialization.detail_text,
    )


__all__ = [
    "DownstreamEvidenceMaterialization",
    "load_downstream_evidence_materialization",
    "load_downstream_evidence_preview_payload",
]
