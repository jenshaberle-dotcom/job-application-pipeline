"""Serve Product V1 Control Center with read-only downstream evidence preview.

This extends the existing read-only Control Center handler with one explicit GET
endpoint. The endpoint reads one current Silver/readiness row, fetches only its
already-validated employer-origin HTTPS detail source, and runs deterministic
Assessment + Ranking evidence previews. It performs no DB write and no LLM call.
"""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig
from scripts.run_product_v1_control_center import ProductV1Handler, build_parser
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


def load_downstream_evidence_preview_payload(silver_job_id: int) -> dict[str, object]:
    """Load one row and return provider-free deterministic downstream preview."""

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
    return build_product_v1_downstream_preview(
        row=row,
        final_url=final_url,
        fetched_title=fetched_title,
        detail_text=detail_text,
    )


class ProductV1PreviewHandler(ProductV1Handler):
    server_version = "DeepOceanProductV1/0.2-preview"

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        if parsed.path != "/api/v1/product-v1/evidence-preview":
            super().do_GET()
            return

        query = parse_qs(parsed.query, keep_blank_values=True)
        raw_ids = query.get("silver_job_id") or []
        if len(raw_ids) != 1:
            self._send_json(
                {
                    "status": "blocked",
                    "reason": "exactly one silver_job_id query parameter is required",
                },
                status=HTTPStatus.BAD_REQUEST,
            )
            return
        try:
            silver_job_id = int(raw_ids[0])
        except (TypeError, ValueError):
            self._send_json(
                {"status": "blocked", "reason": "silver_job_id must be an integer"},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            self._send_json(load_downstream_evidence_preview_payload(silver_job_id))
        except DownstreamPreviewStop as exc:
            self._send_json(
                {
                    "status": "blocked",
                    "reason": str(exc),
                    "provider_requests": 0,
                    "database_writes": 0,
                    "product_authority": False,
                },
                status=HTTPStatus.CONFLICT,
            )
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            self._send_json(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "provider_requests": 0,
                    "database_writes": 0,
                    "product_authority": False,
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )


def run_server(args: argparse.Namespace) -> None:
    server = ThreadingHTTPServer((args.host, args.port), ProductV1PreviewHandler)
    server.frontend_dist = args.frontend_dist  # type: ignore[attr-defined]
    print(f"Deep Ocean Product V1 Control Center: http://{args.host}:{args.port}/")
    print(
        "Boundary: read-only API + deterministic evidence preview; no provider call, "
        "no DB mutation, no source activation, no application submission."
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProduct V1 Control Center stopped by operator.")
    finally:
        server.server_close()


def main() -> None:
    run_server(build_parser().parse_args())


if __name__ == "__main__":
    main()
