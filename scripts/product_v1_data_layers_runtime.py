"""Read-only Bronze/Silver/Gold observability for the Product V1 demo.

This module projects existing database truth only. It creates no telemetry rows,
changes no source or scheduler state, and owns no Product V1 ranking, Top-5 or
application authority.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping, Sequence

import psycopg

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig


SCHEMA_VERSION = "job_application_pipeline.product_v1_data_layers.v1"
FLOW_DAYS = 14


def _relation_exists(conn: psycopg.Connection[Any], relation_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT to_regclass(%s) IS NOT NULL",
            (f"public.{relation_name}",),
        )
        row = cur.fetchone()
    return bool(row and row[0])


def _count_rows(conn: psycopg.Connection[Any], relation_name: str) -> int | None:
    if not _relation_exists(conn, relation_name):
        return None
    allowed = {"raw_jobs", "silver_jobs", "job_product_assessments"}
    if relation_name not in allowed:
        raise ValueError(f"unsupported data-layer relation: {relation_name}")
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*)::bigint FROM {relation_name}")  # noqa: S608
        row = cur.fetchone()
    return int(row[0]) if row else 0


def _daily_counts(
    conn: psycopg.Connection[Any],
    *,
    relation_name: str,
    timestamp_column: str,
    today: date,
) -> dict[date, int] | None:
    allowed = {
        ("raw_jobs", "created_at"),
        ("job_observations", "observed_at"),
        ("silver_jobs", "normalized_at"),
        ("job_product_assessments", "assessed_at"),
    }
    if (relation_name, timestamp_column) not in allowed:
        raise ValueError(
            f"unsupported data-layer flow source: {relation_name}.{timestamp_column}"
        )
    if not _relation_exists(conn, relation_name):
        return None
    start = today - timedelta(days=FLOW_DAYS - 1)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {timestamp_column}::date AS observed_date, count(*)::bigint AS count
            FROM {relation_name}
            WHERE {timestamp_column} >= %s
              AND {timestamp_column} < %s
            GROUP BY {timestamp_column}::date
            ORDER BY observed_date
            """,  # noqa: S608
            (start, today + timedelta(days=1)),
        )
        rows = cur.fetchall()
    return {row[0]: int(row[1]) for row in rows}


def _latest_timestamp(
    conn: psycopg.Connection[Any],
    *,
    relation_name: str,
    timestamp_column: str,
) -> object | None:
    allowed = {
        ("job_observations", "observed_at"),
        ("silver_jobs", "normalized_at"),
        ("job_product_assessments", "assessed_at"),
    }
    if (relation_name, timestamp_column) not in allowed:
        raise ValueError(
            f"unsupported data-layer freshness source: {relation_name}.{timestamp_column}"
        )
    if not _relation_exists(conn, relation_name):
        return None
    with conn.cursor() as cur:
        cur.execute(  # noqa: S608
            f"SELECT max({timestamp_column}) FROM {relation_name}"
        )
        row = cur.fetchone()
    return row[0] if row else None


def _ratio(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round((numerator / denominator) * 100.0, 1)


def _source_rows(product_payload: Mapping[str, object]) -> list[dict[str, object]]:
    overview = product_payload.get("source_connector_overview")
    if not isinstance(overview, Mapping):
        return []
    raw_sources = overview.get("sources")
    if not isinstance(raw_sources, Sequence) or isinstance(raw_sources, (str, bytes)):
        return []

    rows: list[dict[str, object]] = []
    for raw_source in raw_sources:
        if not isinstance(raw_source, Mapping):
            continue
        ingestion = raw_source.get("last_ingestion")
        layers = raw_source.get("layers")
        if not isinstance(ingestion, Mapping):
            ingestion = {}
        if not isinstance(layers, Mapping):
            layers = {}
        rows.append(
            {
                "source_name": str(raw_source.get("source_name") or ""),
                "source_label": str(
                    raw_source.get("source_label")
                    or raw_source.get("source_name")
                    or "unknown"
                ),
                "last_run_at": ingestion.get("finished_at")
                or ingestion.get("started_at"),
                "last_run_status": str(ingestion.get("status") or "unknown"),
                "loaded": int(ingestion.get("total_loaded") or 0),
                "inserted": int(ingestion.get("inserted_count") or 0),
                "bronze": int(layers.get("bronze_count") or 0),
                "silver": int(layers.get("silver_count") or 0),
                "layer_status": str(layers.get("status") or "unknown"),
            }
        )
    rows.sort(
        key=lambda row: (
            int(row["silver"]),
            int(row["bronze"]),
            str(row["source_label"]),
        ),
        reverse=True,
    )
    return rows


def build_data_layers_payload(
    *,
    today: date,
    bronze_count: int | None,
    silver_count: int | None,
    gold_assessed_count: int | None,
    rankable_now: int,
    top_jobs_now: int,
    bronze_flow: Mapping[date, int] | None,
    observation_flow: Mapping[date, int] | None,
    silver_flow: Mapping[date, int] | None,
    gold_flow: Mapping[date, int] | None,
    latest_bronze_observation: object | None,
    latest_silver_normalization: object | None,
    latest_gold_assessment: object | None,
    sources: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Assemble the transport payload without inventing missing history."""

    start = today - timedelta(days=FLOW_DAYS - 1)
    flow: list[dict[str, object]] = []
    for offset in range(FLOW_DAYS):
        current = start + timedelta(days=offset)
        flow.append(
            {
                "date": current.isoformat(),
                "bronze_new": None if bronze_flow is None else bronze_flow.get(current, 0),
                "bronze_observations": (
                    None
                    if observation_flow is None
                    else observation_flow.get(current, 0)
                ),
                "silver_normalized": (
                    None if silver_flow is None else silver_flow.get(current, 0)
                ),
                "gold_assessed": None if gold_flow is None else gold_flow.get(current, 0),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "window_days": FLOW_DAYS,
        "inventory": {
            "bronze_jobs": bronze_count,
            "silver_jobs": silver_count,
            "gold_assessed": gold_assessed_count,
            "rankable_now": rankable_now,
            "top_jobs_now": top_jobs_now,
        },
        "flow": flow,
        "coverage": {
            "bronze_to_silver_pct": _ratio(silver_count, bronze_count),
            "silver_to_gold_pct": _ratio(gold_assessed_count, silver_count),
            "gold_to_rankable_pct": _ratio(rankable_now, gold_assessed_count),
        },
        "freshness": {
            "latest_bronze_observation_at": latest_bronze_observation,
            "latest_silver_normalized_at": latest_silver_normalization,
            "latest_gold_assessed_at": latest_gold_assessment,
        },
        "sources": [dict(source) for source in sources],
        "boundaries": {
            "read_only": True,
            "migration_free": True,
            "creates_telemetry": False,
            "historical_rankable_series_available": False,
            "historical_top5_series_available": False,
            "ranking_authority": False,
            "application_authority": False,
            "source_activation_authority": False,
        },
    }


def load_data_layers_payload(
    product_payload: Mapping[str, object], *, today: date | None = None
) -> dict[str, object]:
    """Read existing DB truth inside an explicitly read-only transaction."""

    current_day = today or date.today()
    summary = product_payload.get("summary")
    if not isinstance(summary, Mapping):
        summary = {}

    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        bronze_count = _count_rows(conn, "raw_jobs")
        silver_count = _count_rows(conn, "silver_jobs")
        gold_count = _count_rows(conn, "job_product_assessments")
        bronze_flow = _daily_counts(
            conn,
            relation_name="raw_jobs",
            timestamp_column="created_at",
            today=current_day,
        )
        observation_flow = _daily_counts(
            conn,
            relation_name="job_observations",
            timestamp_column="observed_at",
            today=current_day,
        )
        silver_flow = _daily_counts(
            conn,
            relation_name="silver_jobs",
            timestamp_column="normalized_at",
            today=current_day,
        )
        gold_flow = _daily_counts(
            conn,
            relation_name="job_product_assessments",
            timestamp_column="assessed_at",
            today=current_day,
        )
        latest_bronze = _latest_timestamp(
            conn,
            relation_name="job_observations",
            timestamp_column="observed_at",
        )
        latest_silver = _latest_timestamp(
            conn,
            relation_name="silver_jobs",
            timestamp_column="normalized_at",
        )
        latest_gold = _latest_timestamp(
            conn,
            relation_name="job_product_assessments",
            timestamp_column="assessed_at",
        )

    return build_data_layers_payload(
        today=current_day,
        bronze_count=bronze_count,
        silver_count=silver_count,
        gold_assessed_count=gold_count,
        rankable_now=int(summary.get("rankable_job_count") or 0),
        top_jobs_now=int(summary.get("top_job_count") or 0),
        bronze_flow=bronze_flow,
        observation_flow=observation_flow,
        silver_flow=silver_flow,
        gold_flow=gold_flow,
        latest_bronze_observation=latest_bronze,
        latest_silver_normalization=latest_silver,
        latest_gold_assessment=latest_gold,
        sources=_source_rows(product_payload),
    )
