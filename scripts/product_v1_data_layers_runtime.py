"""Read-only Bronze/Silver/Gold observability for the current All-jobs cohort.

Every primary count on this surface uses the exact current operator ``All jobs``
population. Historical Bronze/Silver/Gold rows remain database history but are not
mixed into the operator funnel. The projection is read-only and owns no ranking,
source activation or application authority.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping, Sequence

import psycopg

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig


SCHEMA_VERSION = "job_application_pipeline.product_v1_data_layers.v3"
FLOW_DAYS = 14


def _relation_exists(conn: psycopg.Connection[Any], relation_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT to_regclass(%s) IS NOT NULL",
            (f"public.{relation_name}",),
        )
        row = cur.fetchone()
    return bool(row and row[0])


def _ratio(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round((numerator / denominator) * 100.0, 1)


def _collection_ids(value: object) -> set[int]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return set()
    result: set[int] = set()
    for row in value:
        if not isinstance(row, Mapping) or row.get("silver_job_id") is None:
            continue
        try:
            result.add(int(row["silver_job_id"]))
        except (TypeError, ValueError):
            continue
    return result


def _current_cohort(
    conn: psycopg.Connection[Any],
    product_payload: Mapping[str, object],
) -> dict[str, object]:
    current_ids = _collection_ids(product_payload.get("job_readiness"))
    all_jobs = len(current_ids)
    if not current_ids:
        return {
            "ids": current_ids,
            "all_jobs": 0,
            "bronze_jobs": 0,
            "silver_jobs": 0,
            "gold_assessed": 0,
        }

    params = (list(sorted(current_ids)),)
    with conn.cursor() as cur:
        if _relation_exists(conn, "silver_jobs") and _relation_exists(conn, "raw_jobs"):
            cur.execute(
                """
                SELECT count(*)::integer
                FROM silver_jobs silver
                JOIN raw_jobs raw ON raw.id = silver.raw_job_id
                WHERE silver.id = ANY(%s)
                """,
                params,
            )
            bronze_jobs = int(cur.fetchone()[0] or 0)
        else:
            bronze_jobs = 0

        if _relation_exists(conn, "silver_jobs"):
            cur.execute(
                "SELECT count(*)::integer FROM silver_jobs WHERE id = ANY(%s)",
                params,
            )
            silver_jobs = int(cur.fetchone()[0] or 0)
        else:
            silver_jobs = 0

        if _relation_exists(conn, "job_product_assessments"):
            cur.execute(
                """
                SELECT count(*)::integer
                FROM job_product_assessments
                WHERE silver_job_id = ANY(%s)
                """,
                params,
            )
            gold_assessed = int(cur.fetchone()[0] or 0)
        else:
            gold_assessed = 0

    return {
        "ids": current_ids,
        "all_jobs": all_jobs,
        "bronze_jobs": bronze_jobs,
        "silver_jobs": silver_jobs,
        "gold_assessed": gold_assessed,
    }


def _daily_current_counts(
    conn: psycopg.Connection[Any],
    *,
    current_ids: set[int],
    layer: str,
    today: date,
) -> dict[date, int] | None:
    if not current_ids:
        return {}
    start = today - timedelta(days=FLOW_DAYS - 1)
    ids = list(sorted(current_ids))
    queries = {
        "bronze": (
            {"raw_jobs", "silver_jobs"},
            """
            SELECT raw.created_at::date AS observed_date, count(*)::bigint
            FROM silver_jobs silver
            JOIN raw_jobs raw ON raw.id = silver.raw_job_id
            WHERE silver.id = ANY(%s)
              AND raw.created_at >= %s
              AND raw.created_at < %s
            GROUP BY raw.created_at::date
            ORDER BY observed_date
            """,
        ),
        "silver": (
            {"silver_jobs"},
            """
            SELECT normalized_at::date AS observed_date, count(*)::bigint
            FROM silver_jobs
            WHERE id = ANY(%s)
              AND normalized_at >= %s
              AND normalized_at < %s
            GROUP BY normalized_at::date
            ORDER BY observed_date
            """,
        ),
        "gold": (
            {"job_product_assessments"},
            """
            SELECT assessed_at::date AS observed_date, count(*)::bigint
            FROM job_product_assessments
            WHERE silver_job_id = ANY(%s)
              AND assessed_at >= %s
              AND assessed_at < %s
            GROUP BY assessed_at::date
            ORDER BY observed_date
            """,
        ),
    }
    required, query = queries[layer]
    if not all(_relation_exists(conn, relation) for relation in required):
        return None
    with conn.cursor() as cur:
        cur.execute(query, (ids, start, today + timedelta(days=1)))
        rows = cur.fetchall()
    return {row[0]: int(row[1]) for row in rows}


def _current_freshness(
    conn: psycopg.Connection[Any], current_ids: set[int]
) -> dict[str, object | None]:
    result: dict[str, object | None] = {
        "latest_bronze_observation_at": None,
        "latest_silver_normalized_at": None,
        "latest_gold_assessed_at": None,
    }
    if not current_ids:
        return result
    ids = list(sorted(current_ids))
    with conn.cursor() as cur:
        if (
            _relation_exists(conn, "job_observations")
            and _relation_exists(conn, "silver_jobs")
        ):
            cur.execute(
                """
                SELECT max(observation.observed_at)
                FROM silver_jobs silver
                JOIN job_observations observation
                  ON observation.raw_job_id = silver.raw_job_id
                WHERE silver.id = ANY(%s)
                  AND observation.is_seen = TRUE
                """,
                (ids,),
            )
            row = cur.fetchone()
            result["latest_bronze_observation_at"] = row[0] if row else None
        if _relation_exists(conn, "silver_jobs"):
            cur.execute(
                "SELECT max(normalized_at) FROM silver_jobs WHERE id = ANY(%s)",
                (ids,),
            )
            row = cur.fetchone()
            result["latest_silver_normalized_at"] = row[0] if row else None
        if _relation_exists(conn, "job_product_assessments"):
            cur.execute(
                """
                SELECT max(assessed_at)
                FROM job_product_assessments
                WHERE silver_job_id = ANY(%s)
                """,
                (ids,),
            )
            row = cur.fetchone()
            result["latest_gold_assessed_at"] = row[0] if row else None
    return result


def build_data_layers_payload(
    *,
    today: date,
    all_jobs: int,
    bronze_count: int,
    silver_count: int,
    gold_assessed_count: int,
    rankable_now: int,
    top_jobs_now: int,
    bronze_flow: Mapping[date, int] | None,
    silver_flow: Mapping[date, int] | None,
    gold_flow: Mapping[date, int] | None,
    latest_bronze_observation: object | None,
    latest_silver_normalization: object | None,
    latest_gold_assessment: object | None,
) -> dict[str, object]:
    """Assemble one population-consistent operator payload."""

    start = today - timedelta(days=FLOW_DAYS - 1)
    flow: list[dict[str, object]] = []
    for offset in range(FLOW_DAYS):
        current = start + timedelta(days=offset)
        flow.append(
            {
                "date": current.isoformat(),
                "bronze_new": None if bronze_flow is None else bronze_flow.get(current, 0),
                "silver_normalized": (
                    None if silver_flow is None else silver_flow.get(current, 0)
                ),
                "gold_assessed": None if gold_flow is None else gold_flow.get(current, 0),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "window_days": FLOW_DAYS,
        "population": {
            "key": "current_all_jobs",
            "label": "Current All jobs",
            "all_jobs": all_jobs,
        },
        "layers": {
            "bronze_jobs": bronze_count,
            "silver_jobs": silver_count,
            "gold_assessed": gold_assessed_count,
            "rankable_now": rankable_now,
            "top_jobs_now": top_jobs_now,
        },
        "coverage": {
            "bronze_to_silver_pct": _ratio(silver_count, bronze_count),
            "silver_to_gold_pct": _ratio(gold_assessed_count, silver_count),
            "all_jobs_gold_assessed_pct": _ratio(gold_assessed_count, all_jobs),
        },
        "flow": flow,
        "freshness": {
            "latest_bronze_observation_at": latest_bronze_observation,
            "latest_silver_normalized_at": latest_silver_normalization,
            "latest_gold_assessed_at": latest_gold_assessment,
        },
        "boundaries": {
            "read_only": True,
            "migration_free": True,
            "creates_telemetry": False,
            "historical_rankable_series_available": False,
            "historical_top5_series_available": False,
            "ranking_authority": False,
            "application_authority": False,
            "source_activation_authority": False,
            "single_population_current_all_jobs": True,
            "historical_inventory_excluded_from_primary_counts": True,
            "repeat_observations_excluded_from_primary_flow": True,
        },
    }


def load_data_layers_payload(
    product_payload: Mapping[str, object], *, today: date | None = None
) -> dict[str, object]:
    """Read one current-cohort layer projection in an explicit read-only transaction."""

    current_day = today or date.today()
    summary = product_payload.get("summary")
    if not isinstance(summary, Mapping):
        summary = {}

    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        cohort = _current_cohort(conn, product_payload)
        current_ids = cohort["ids"]
        assert isinstance(current_ids, set)
        bronze_flow = _daily_current_counts(
            conn, current_ids=current_ids, layer="bronze", today=current_day
        )
        silver_flow = _daily_current_counts(
            conn, current_ids=current_ids, layer="silver", today=current_day
        )
        gold_flow = _daily_current_counts(
            conn, current_ids=current_ids, layer="gold", today=current_day
        )
        freshness = _current_freshness(conn, current_ids)
        conn.rollback()

    return build_data_layers_payload(
        today=current_day,
        all_jobs=int(cohort["all_jobs"]),
        bronze_count=int(cohort["bronze_jobs"]),
        silver_count=int(cohort["silver_jobs"]),
        gold_assessed_count=int(cohort["gold_assessed"]),
        rankable_now=int(summary.get("rankable_job_count") or 0),
        top_jobs_now=int(summary.get("top_job_count") or 0),
        bronze_flow=bronze_flow,
        silver_flow=silver_flow,
        gold_flow=gold_flow,
        latest_bronze_observation=freshness["latest_bronze_observation_at"],
        latest_silver_normalization=freshness["latest_silver_normalized_at"],
        latest_gold_assessment=freshness["latest_gold_assessed_at"],
    )
