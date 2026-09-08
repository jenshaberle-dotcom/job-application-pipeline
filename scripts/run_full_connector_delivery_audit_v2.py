"""Corrections for the P1 full connector delivery audit.

V1 intentionally reused production helper functions but exposed two audit-harness
mistakes during the first real run:
- StepStone suppression helper is keyword-only.
- Control Center 'current' truth is lifecycle_status=active_confirmed, not the
  older activity_status compatibility field.

This wrapper patches only those audit semantics, then executes the same read-only
full inventory/live connector audit.
"""
from __future__ import annotations

import psycopg

from scripts import run_full_connector_delivery_audit as audit
from src.ingestion.aggregator_discovery_filter import (
    filter_known_employer_origin_candidates as production_filter,
)


_original_db_snapshot = audit.db_snapshot
_original_build_report = audit.build_report


def _stepstone_filter(records, excluded_company_keys):
    return production_filter(
        records=records,
        excluded_company_keys=excluded_company_keys,
    )


def _corrected_db_snapshot():
    snapshot = _original_db_snapshot()
    with psycopg.connect(**audit.get_database_config()) as conn:
        audit.require_read_only(conn)
        if not (
            audit.relation_exists(conn, "gold_product_v1_job_readiness")
            and audit.relation_exists(conn, "silver_jobs")
        ):
            snapshot["gold"] = []
            return snapshot

        readiness_columns = audit.columns(conn, "gold_product_v1_job_readiness")
        lifecycle = "lifecycle_status" in readiness_columns
        rankable = "product_readiness_status" in readiness_columns
        current_expr = (
            "COUNT(*) FILTER (WHERE r.lifecycle_status='active_confirmed')"
            if lifecycle
            else "0::bigint"
        )
        stale_expr = (
            "COUNT(*) FILTER (WHERE r.lifecycle_status='stale_needs_refresh')"
            if lifecycle
            else "0::bigint"
        )
        inactive_expr = (
            "COUNT(*) FILTER (WHERE r.lifecycle_status='inactive_confirmed')"
            if lifecycle
            else "0::bigint"
        )
        unverifiable_expr = (
            "COUNT(*) FILTER (WHERE r.lifecycle_status='unverifiable')"
            if lifecycle
            else "0::bigint"
        )
        rankable_expr = (
            "COUNT(*) FILTER (WHERE r.product_readiness_status='rankable')"
            if rankable
            else "0::bigint"
        )
        snapshot["gold"] = audit.fetch_all(
            conn,
            f"""
            SELECT
                s.source_name,
                COUNT(*) AS cc_total,
                {current_expr} AS cc_active,
                {stale_expr} AS cc_stale,
                {inactive_expr} AS cc_inactive,
                {unverifiable_expr} AS cc_unverifiable,
                {rankable_expr} AS cc_rankable
            FROM gold_product_v1_job_readiness r
            JOIN silver_jobs s ON s.id=r.silver_job_id
            GROUP BY s.source_name
            ORDER BY s.source_name
            """,
        )
    return snapshot


def _corrected_build_report():
    report = _original_build_report()
    report["schema"] = "job_application_pipeline.full_connector_delivery_audit.v2"
    sources = report.get("sources") or []
    report["summary"].update(
        {
            "cc_readiness_rows": sum(
                int((source.get("db_state") or {}).get("cc_total") or 0)
                for source in sources
            ),
            "cc_current_active_confirmed": sum(
                int((source.get("db_state") or {}).get("cc_active") or 0)
                for source in sources
            ),
            "cc_stale_needs_refresh": sum(
                int((source.get("db_state") or {}).get("cc_stale") or 0)
                for source in sources
            ),
            "cc_inactive_confirmed": sum(
                int((source.get("db_state") or {}).get("cc_inactive") or 0)
                for source in sources
            ),
            "cc_unverifiable": sum(
                int((source.get("db_state") or {}).get("cc_unverifiable") or 0)
                for source in sources
            ),
            "cc_rankable": sum(
                int((source.get("db_state") or {}).get("cc_rankable") or 0)
                for source in sources
            ),
        }
    )
    return report


audit.filter_known_employer_origin_candidates = _stepstone_filter
audit.db_snapshot = _corrected_db_snapshot
audit.build_report = _corrected_build_report


if __name__ == "__main__":
    raise SystemExit(audit.main())
