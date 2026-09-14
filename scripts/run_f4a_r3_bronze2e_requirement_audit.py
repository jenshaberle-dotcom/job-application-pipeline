"""Audit F4A-R3 requirement evidence from Bronze through Product/operator truth.

The audit is read-only and provider-free. It compares the strongest persisted
Bronze/observation evidence available for each current operator-review job with
what the current Product assessment exposes. Its purpose is to distinguish real
source absence from Bronze->Silver/Product transport loss before the vertical
Bronze2E repair is accepted.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from scripts import run_f4a_r2_current_requirement_origin_diagnostic as current_scope
from src.config import get_database_config
from src.silver.requirement_evidence_projection import build_silver_requirement_evidence


SCHEMA = "job_application_pipeline.f4a_r3_bronze2e_requirement_audit.v1"
TARGET_FIELDS = (
    "employment_type",
    "required_languages",
    "weekly_hours",
    "work_model",
    "requirements_seniority",
    "job_skills",
)
_OBSERVED_STATUSES = frozenset({"observed_structured", "observed_bounded_text"})


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _source_family(source_name: object) -> str:
    return str(source_name or "").split(":", 1)[0] or "unknown"


def _review_ids() -> set[int]:
    return current_scope._review_scope_ids(current_scope._operator_review_payload())


def _load_rows(conn: psycopg.Connection[Any], review_ids: set[int]) -> list[dict[str, Any]]:
    if not review_ids:
        return []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                s.id AS silver_job_id,
                s.raw_job_id,
                s.source_name,
                s.source_url,
                s.title,
                s.company_name,
                r.raw_data,
                latest.normalized_evidence,
                a.employment_type,
                a.required_languages,
                a.weekly_hours_min,
                a.weekly_hours_max,
                a.work_model,
                a.requirements_seniority,
                a.ranking_factors -> 'requirement_evidence' AS product_requirement_evidence
            FROM silver_jobs s
            JOIN raw_jobs r ON r.id = s.raw_job_id
            LEFT JOIN job_product_assessments a ON a.silver_job_id = s.id
            LEFT JOIN LATERAL (
                SELECT o.normalized_evidence
                FROM job_observations o
                WHERE o.raw_job_id = s.raw_job_id
                  AND o.normalized_evidence IS NOT NULL
                ORDER BY o.observed_at DESC, o.id DESC
                LIMIT 1
            ) latest ON TRUE
            WHERE s.id = ANY(%s)
            ORDER BY s.source_name, s.id
            """,
            (sorted(review_ids),),
        )
        return [dict(row) for row in cur.fetchall()]


def _best_raw_data(row: Mapping[str, Any]) -> tuple[Mapping[str, Any], str]:
    normalized = _mapping(row.get("normalized_evidence"))
    observed_raw = normalized.get("raw_evidence")
    if isinstance(observed_raw, Mapping):
        return observed_raw, "latest_observation"
    raw = row.get("raw_data")
    if isinstance(raw, Mapping):
        return raw, "raw_jobs"
    return {}, "missing"


def _product_present(row: Mapping[str, Any], field: str) -> bool:
    if field == "employment_type":
        return str(row.get("employment_type") or "unknown") != "unknown"
    if field == "required_languages":
        return bool(row.get("required_languages"))
    if field == "weekly_hours":
        return row.get("weekly_hours_min") is not None or row.get("weekly_hours_max") is not None
    if field == "work_model":
        return str(row.get("work_model") or "unknown") != "unknown"
    if field == "requirements_seniority":
        return str(row.get("requirements_seniority") or "unknown") != "unknown"
    if field == "job_skills":
        evidence = _mapping(row.get("product_requirement_evidence"))
        skills = evidence.get("job_skills")
        return isinstance(skills, list) and bool(skills)
    raise KeyError(field)


def _classification(bronze_field: Mapping[str, Any], product_present: bool) -> str:
    status = str(bronze_field.get("status") or "")
    bronze_present = status in _OBSERVED_STATUSES
    if bronze_present and product_present:
        return "preserved_or_rederived"
    if bronze_present and not product_present:
        return "bronze_truth_lost_before_product"
    if not bronze_present and product_present:
        return "product_only_origin_reparse"
    if status == "conflict":
        return "conflict_fail_closed"
    return "source_absent_or_unresolved"


def build_report(rows: list[Mapping[str, Any]]) -> dict[str, object]:
    field_counts: dict[str, Counter[str]] = {field: Counter() for field in TARGET_FIELDS}
    family_counts: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: {field: Counter() for field in TARGET_FIELDS}
    )
    parser_families: Counter[str] = Counter()
    evidence_sources: Counter[str] = Counter()
    row_reports: list[dict[str, object]] = []

    for row in rows:
        raw_data, raw_source = _best_raw_data(row)
        raw_job = {
            "id": row.get("raw_job_id"),
            "source_name": row.get("source_name"),
            "source_url": row.get("source_url"),
            "title": row.get("title"),
            "raw_data": raw_data,
        }
        projected = build_silver_requirement_evidence(raw_job)
        fields = _mapping(projected.get("fields"))
        family = _source_family(row.get("source_name"))
        parser_family = str(projected.get("parser_family") or "unclassified")
        parser_families[parser_family] += 1
        evidence_sources[raw_source] += 1

        classifications: dict[str, str] = {}
        statuses: dict[str, str] = {}
        for field in TARGET_FIELDS:
            bronze_field = _mapping(fields.get(field))
            status = str(bronze_field.get("status") or "missing")
            classification = _classification(bronze_field, _product_present(row, field))
            statuses[field] = status
            classifications[field] = classification
            field_counts[field][classification] += 1
            family_counts[family][field][classification] += 1

        row_reports.append(
            {
                "silver_job_id": int(row["silver_job_id"]),
                "source_name": row.get("source_name"),
                "source_family": family,
                "title": row.get("title"),
                "company_name": row.get("company_name"),
                "bronze_evidence_source": raw_source,
                "parser_family": parser_family,
                "structured_jobposting_found": projected.get("structured_jobposting_found"),
                "bronze_status": statuses,
                "classification": classifications,
            }
        )

    lost_rows = [
        row
        for row in row_reports
        if "bronze_truth_lost_before_product" in row["classification"].values()
    ]
    product_only_rows = [
        row
        for row in row_reports
        if "product_only_origin_reparse" in row["classification"].values()
    ]

    return {
        "schema": SCHEMA,
        "mode": "read_only",
        "candidate_count": len(rows),
        "parser_family_counts": dict(sorted(parser_families.items())),
        "bronze_evidence_source_counts": dict(sorted(evidence_sources.items())),
        "field_classification_counts": {
            field: dict(sorted(counts.items())) for field, counts in field_counts.items()
        },
        "source_family_field_counts": {
            family: {
                field: dict(sorted(counts.items()))
                for field, counts in fields.items()
            }
            for family, fields in sorted(family_counts.items())
        },
        "rows_with_bronze_truth_lost_before_product": len(lost_rows),
        "rows_with_product_only_origin_reparse": len(product_only_rows),
        "lost_rows": lost_rows,
        "product_only_rows": product_only_rows,
        "rows": row_reports,
        "boundaries": {
            "database_writes": 0,
            "provider_calls": 0,
            "candidate_fact_reads": 0,
            "ranking_authority": 0,
            "top5_authority": 0,
            "application_authority": 0,
            "raw_html_persisted": 0,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    review_ids = _review_ids()
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        rows = _load_rows(conn, review_ids)
        conn.rollback()

    report = build_report(rows)
    print(f"F4A_R3_BRONZE2E_CANDIDATE_COUNT={report['candidate_count']}")
    print(
        "F4A_R3_BRONZE2E_PARSER_FAMILIES="
        + json.dumps(report["parser_family_counts"], sort_keys=True)
    )
    print(
        "F4A_R3_BRONZE2E_FIELD_COUNTS="
        + json.dumps(report["field_classification_counts"], sort_keys=True)
    )
    print(
        "F4A_R3_BRONZE2E_LOST_ROWS="
        + str(report["rows_with_bronze_truth_lost_before_product"])
    )
    print(
        "F4A_R3_BRONZE2E_PRODUCT_ONLY_ROWS="
        + str(report["rows_with_product_only_origin_reparse"])
    )
    print("F4A_R3_BRONZE2E_AUDIT=PASS")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
