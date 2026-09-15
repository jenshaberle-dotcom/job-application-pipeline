"""Audit F4A requirement evidence from Bronze through persisted Silver to operator truth.

This audit is read-only and provider-free. It binds the lifecycle-current operator
review cohort to the strongest persisted Bronze/observation evidence, the durable
Silver requirement sidecar, and the exact enriched Product payload shown to the
operator. It never creates Candidate Facts, fit, ranking, Top-5 or application
authority.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from scripts import product_v1_control_center_base
from scripts.product_v1_job_presentation_runtime import enrich_product_payload_for_operator
from src.config import get_database_config
from src.silver.requirement_evidence_projection import (
    SILVER_REQUIREMENT_EVIDENCE_SCHEMA,
    build_silver_requirement_evidence,
)


SCHEMA = "job_application_pipeline.f4a_r4_bronze2e_requirement_audit.v3"
MIN_REACHABLE_COVERAGE_RATIO = 0.80
TARGET_FIELDS = (
    "employment_type",
    "required_languages",
    "weekly_hours",
    "work_model",
    "requirements_seniority",
    "job_skills",
)
CONTEXT_DIMENSIONS = (
    "employment_scope",
    "structured_work_hours",
    "posting_language",
    "experience",
    "compensation",
    "collective_agreement",
    "title_seniority",
)
_OBSERVED_STATUSES = frozenset({"observed_structured", "observed_bounded_text"})
_EXPLICIT_MISSING_STATUSES = frozenset(
    {"source_absent", "extractor_gap", "conflict", "origin_unavailable"}
)
_ALLOWED_STATUSES = _OBSERVED_STATUSES | _EXPLICIT_MISSING_STATUSES
_LEGACY_AMBIGUOUS_STATUS = "source_absent_or_unresolved"


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _source_family(source_name: object) -> str:
    return str(source_name or "").split(":", 1)[0] or "unknown"


def _review_payload() -> dict[str, object]:
    core = product_v1_control_center_base.load_product_v1_payload(
        include_source_connector_overview=False
    )
    return enrich_product_payload_for_operator(core)


def _operator_rows(payload: Mapping[str, object]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    rows = payload.get("job_readiness")
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        try:
            silver_job_id = int(row.get("silver_job_id") or 0)
        except (TypeError, ValueError):
            continue
        if silver_job_id > 0:
            result[silver_job_id] = row
    return result


def _load_rows(
    conn: psycopg.Connection[Any], review_ids: set[int]
) -> list[dict[str, Any]]:
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
                sidecar.evidence_hash AS persisted_evidence_hash,
                sidecar.evidence_payload AS persisted_silver_requirement_evidence
            FROM silver_jobs s
            JOIN raw_jobs r ON r.id = s.raw_job_id
            LEFT JOIN silver_job_requirement_evidence sidecar
              ON sidecar.silver_job_id = s.id
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


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _field_status(payload: Mapping[str, Any], field: str) -> str:
    fields = _mapping(payload.get("fields"))
    return str(_mapping(fields.get(field)).get("status") or "missing")


def _field_value(payload: Mapping[str, Any], field: str) -> object:
    value = _mapping(_mapping(payload.get("fields")).get(field))
    if field in {"employment_type", "work_model", "requirements_seniority"}:
        return str(value.get("value") or "unknown")
    if field in {"required_languages", "job_skills"}:
        raw = value.get("values")
        return tuple(str(item) for item in raw) if isinstance(raw, list) else ()
    if field == "weekly_hours":
        return (value.get("minimum"), value.get("maximum"))
    raise KeyError(field)


def _operator_value(row: Mapping[str, Any], field: str) -> object:
    if field in {"employment_type", "work_model", "requirements_seniority"}:
        return str(row.get(field) or "unknown")
    if field in {"required_languages", "job_skills"}:
        raw = row.get(field)
        return tuple(str(item) for item in raw) if isinstance(raw, list) else ()
    if field == "weekly_hours":
        return (row.get("weekly_hours_min"), row.get("weekly_hours_max"))
    raise KeyError(field)


def _operator_status(row: Mapping[str, Any], field: str) -> str:
    key = {
        "employment_type": "employment_evidence_status",
        "required_languages": "language_evidence_status",
        "weekly_hours": "weekly_hours_evidence_status",
        "work_model": "work_model_resolution",
        "requirements_seniority": "seniority_evidence_status",
    }.get(field)
    if key is not None:
        return str(row.get(key) or "missing")
    unresolved = row.get("requirement_unresolved_fields")
    if isinstance(unresolved, list) and field in unresolved:
        return "unresolved"
    return "observed" if _operator_value(row, field) else "source_absent"


def _operator_value_is_missing(value: object, field: str) -> bool:
    if field in {"required_languages", "job_skills"}:
        return value == ()
    if field == "weekly_hours":
        return value == (None, None)
    return value in {None, "", "unknown"}


def _operator_matches_silver(
    silver_payload: Mapping[str, Any],
    operator_row: Mapping[str, Any],
    field: str,
) -> bool:
    status = _field_status(silver_payload, field)
    silver_value = _field_value(silver_payload, field)
    operator_value = _operator_value(operator_row, field)

    if status in _OBSERVED_STATUSES:
        if silver_value != operator_value:
            return False
    elif not _operator_value_is_missing(operator_value, field):
        return False

    if field != "job_skills" and _operator_status(operator_row, field) != status:
        return False
    return True


def _context_signature(payload: Mapping[str, Any]) -> dict[str, tuple[object, ...]]:
    context = _mapping(payload.get("display_context"))
    compensation = _mapping(context.get("compensation"))
    return {
        "employment_scope": (
            str(context.get("employment_scope") or "unknown"),
            str(context.get("employment_scope_status") or "source_absent"),
        ),
        "structured_work_hours": (
            context.get("structured_work_hours"),
            str(context.get("structured_work_hours_status") or "source_absent"),
        ),
        "posting_language": (
            str(context.get("posting_language") or "unknown"),
            str(context.get("posting_language_basis") or "unknown"),
        ),
        "experience": (
            context.get("experience_requirement"),
            context.get("experience_months"),
            context.get("experience_min_months"),
            context.get("experience_max_months"),
            str(context.get("experience_requirement_status") or "source_absent"),
        ),
        "compensation": (
            compensation.get("amount"),
            compensation.get("currency"),
            compensation.get("period"),
            compensation.get("qualifier"),
            str(context.get("compensation_status") or "source_absent"),
        ),
        "collective_agreement": (
            context.get("collective_agreement") is True,
            str(context.get("collective_agreement_status") or "source_absent"),
        ),
        "title_seniority": (
            str(context.get("title_seniority_signal") or "unknown"),
            str(context.get("title_seniority_basis") or "unknown"),
        ),
    }


def _operator_context_signature(row: Mapping[str, Any]) -> dict[str, tuple[object, ...]]:
    return {
        "employment_scope": (
            str(row.get("employment_scope") or "unknown"),
            str(row.get("employment_scope_status") or "source_absent"),
        ),
        "structured_work_hours": (
            row.get("structured_work_hours"),
            str(row.get("structured_work_hours_status") or "source_absent"),
        ),
        "posting_language": (
            str(row.get("posting_language") or "unknown"),
            str(row.get("posting_language_basis") or "unknown"),
        ),
        "experience": (
            row.get("experience_requirement"),
            row.get("experience_months"),
            row.get("experience_min_months"),
            row.get("experience_max_months"),
            str(row.get("experience_requirement_status") or "source_absent"),
        ),
        "compensation": (
            row.get("compensation_amount"),
            row.get("compensation_currency"),
            row.get("compensation_period"),
            row.get("compensation_qualifier"),
            str(row.get("compensation_status") or "source_absent"),
        ),
        "collective_agreement": (
            row.get("collective_agreement") is True,
            str(row.get("collective_agreement_status") or "source_absent"),
        ),
        "title_seniority": (
            str(row.get("title_seniority_signal") or "unknown"),
            str(row.get("title_seniority_basis") or "unknown"),
        ),
    }


def _context_projection_mismatches(
    silver_payload: Mapping[str, Any], operator_row: Mapping[str, Any]
) -> list[str]:
    silver = _context_signature(silver_payload)
    operator = _operator_context_signature(operator_row)
    return [
        f"context:{dimension}"
        for dimension in CONTEXT_DIMENSIONS
        if silver[dimension] != operator[dimension]
    ]


def _authority_safe(payload: Mapping[str, Any]) -> bool:
    authority = _mapping(payload.get("authority"))
    context = _mapping(payload.get("display_context"))
    return (
        authority.get("job_source_evidence_only") is True
        and authority.get("candidate_fact_authority") is False
        and authority.get("capability_fit_authority") is False
        and authority.get("hard_filter_authority") is False
        and authority.get("ranking_authority") is False
        and authority.get("top5_authority") is False
        and authority.get("application_authority") is False
        and context.get("observer_authority") in (None, False)
        and payload.get("raw_html_persisted") is False
    )


def build_report(
    rows: list[Mapping[str, Any]],
    *,
    operator_rows: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, object]:
    operator_by_id = dict(operator_rows or {})
    field_counts: dict[str, Counter[str]] = {
        field: Counter() for field in TARGET_FIELDS
    }
    family_gap_counts: dict[str, Counter[str]] = defaultdict(Counter)
    parser_families: Counter[str] = Counter()
    bronze_sources: Counter[str] = Counter()
    context_observed_counts: Counter[str] = Counter()
    row_reports: list[dict[str, object]] = []

    for row in rows:
        silver_job_id = int(row["silver_job_id"])
        raw_data, raw_source = _best_raw_data(row)
        bronze_projection = build_silver_requirement_evidence(
            {
                "id": row.get("raw_job_id"),
                "source_name": row.get("source_name"),
                "source_url": row.get("source_url"),
                "title": row.get("title"),
                "raw_data": raw_data,
            }
        )
        persisted_raw = row.get("persisted_silver_requirement_evidence")
        persisted = dict(persisted_raw) if isinstance(persisted_raw, Mapping) else {}
        operator = operator_by_id.get(silver_job_id)
        family = _source_family(row.get("source_name"))
        parser_family = str(persisted.get("parser_family") or "missing")
        parser_families[parser_family] += 1
        bronze_sources[raw_source] += 1

        violations: list[str] = []
        if not persisted:
            violations.append("missing_persisted_silver_sidecar")
        elif persisted.get("schema") != SILVER_REQUIREMENT_EVIDENCE_SCHEMA:
            violations.append("invalid_silver_sidecar_schema")

        persisted_hash = str(row.get("persisted_evidence_hash") or "")
        if persisted and persisted_hash != _canonical_hash(persisted):
            violations.append("persisted_silver_sidecar_hash_mismatch")
        if persisted and not _authority_safe(persisted):
            violations.append("silver_sidecar_authority_or_raw_html_violation")

        statuses = {field: _field_status(persisted, field) for field in TARGET_FIELDS}
        bronze_statuses = {
            field: _field_status(bronze_projection, field) for field in TARGET_FIELDS
        }
        legacy_fields = [
            field
            for field, status in statuses.items()
            if status == _LEGACY_AMBIGUOUS_STATUS
        ]
        invalid_fields = [
            field
            for field, status in statuses.items()
            if status not in _ALLOWED_STATUSES and status != _LEGACY_AMBIGUOUS_STATUS
        ]
        gap_fields = [
            field for field, status in statuses.items() if status == "extractor_gap"
        ]
        if legacy_fields:
            violations.append("legacy_ambiguous_requirement_status")
        if invalid_fields:
            violations.append("invalid_requirement_status")

        source_state = (
            "origin_unavailable" if parser_family == "origin_unavailable" else "reachable"
        )
        if source_state == "origin_unavailable":
            non_unavailable = [
                field
                for field, status in statuses.items()
                if status != "origin_unavailable"
            ]
            if non_unavailable:
                violations.append("origin_unavailable_row_has_non_unavailable_field_status")

        operator_uses_silver = (
            operator is not None
            and operator.get("requirement_evidence_source")
            == "silver_job_requirement_evidence"
        )
        if not operator_uses_silver:
            violations.append("operator_not_consuming_silver_sidecar")

        projection_mismatches: list[str] = []
        if operator is not None and operator_uses_silver:
            projection_mismatches = [
                field
                for field in TARGET_FIELDS
                if not _operator_matches_silver(persisted, operator, field)
            ]
            projection_mismatches.extend(
                _context_projection_mismatches(persisted, operator)
            )
            if projection_mismatches:
                violations.append("silver_to_operator_projection_loss")

        refresh_bound = bool(_mapping(persisted.get("refresh_binding")))
        bronze_matches_persisted = all(
            _field_status(bronze_projection, field) == statuses[field]
            and _field_value(bronze_projection, field) == _field_value(persisted, field)
            for field in TARGET_FIELDS
        ) and _context_signature(bronze_projection) == _context_signature(persisted)

        for field, status in statuses.items():
            field_counts[field][status] += 1
            if status == "extractor_gap":
                family_gap_counts[family][field] += 1

        context_signature = _context_signature(persisted)
        for dimension, values in context_signature.items():
            status = str(values[-1] or "")
            if status.startswith("observed_") or (
                dimension == "posting_language" and values[0] != "unknown"
            ) or (
                dimension == "title_seniority" and values[0] != "unknown"
            ):
                context_observed_counts[dimension] += 1

        row_reports.append(
            {
                "silver_job_id": silver_job_id,
                "source_name": row.get("source_name"),
                "source_family": family,
                "title": row.get("title"),
                "company_name": row.get("company_name"),
                "bronze_evidence_source": raw_source,
                "source_state": source_state,
                "parser_family": parser_family,
                "bronze_status": bronze_statuses,
                "silver_status": statuses,
                "silver_context": context_signature,
                "legacy_ambiguous_fields": legacy_fields,
                "invalid_status_fields": invalid_fields,
                "extractor_gap_fields": gap_fields,
                "refresh_bound": refresh_bound,
                "bronze_matches_persisted": bronze_matches_persisted,
                "operator_uses_silver": operator_uses_silver,
                "operator_projection_mismatches": projection_mismatches,
                "violations": sorted(set(violations)),
            }
        )

    reachable = [row for row in row_reports if row["source_state"] == "reachable"]
    reachable_without_gap = [
        row for row in reachable if not row["extractor_gap_fields"]
    ]
    coverage_ratio = len(reachable_without_gap) / len(reachable) if reachable else 0.0
    legacy_rows = [row for row in row_reports if row["legacy_ambiguous_fields"]]
    projection_loss_rows = [
        row for row in row_reports if row["operator_projection_mismatches"]
    ]
    violating_rows = [row for row in row_reports if row["violations"]]
    extractor_gap_rows = [row for row in reachable if row["extractor_gap_fields"]]

    return {
        "schema": SCHEMA,
        "mode": "read_only",
        "candidate_count": len(rows),
        "operator_candidate_count": len(operator_by_id),
        "reachable_count": len(reachable),
        "origin_unavailable_count": len(row_reports) - len(reachable),
        "reachable_without_extractor_gap_count": len(reachable_without_gap),
        "reachable_without_extractor_gap_ratio": coverage_ratio,
        "minimum_reachable_coverage_ratio": MIN_REACHABLE_COVERAGE_RATIO,
        "coverage_gate_pass": (
            bool(reachable)
            and coverage_ratio >= MIN_REACHABLE_COVERAGE_RATIO
            and not legacy_rows
            and not projection_loss_rows
            and not violating_rows
            and len(rows) == len(operator_by_id)
        ),
        "parser_family_counts": dict(sorted(parser_families.items())),
        "bronze_evidence_source_counts": dict(sorted(bronze_sources.items())),
        "field_status_counts": {
            field: dict(sorted(counts.items())) for field, counts in field_counts.items()
        },
        "context_observed_counts": dict(sorted(context_observed_counts.items())),
        "extractor_gap_source_family_counts": {
            family: dict(sorted(counts.items()))
            for family, counts in sorted(family_gap_counts.items())
        },
        "rows_with_extractor_gap": len(extractor_gap_rows),
        "rows_with_legacy_ambiguous_status": len(legacy_rows),
        "rows_with_silver_to_operator_projection_loss": len(projection_loss_rows),
        "violating_row_count": len(violating_rows),
        "extractor_gap_rows": extractor_gap_rows,
        "legacy_ambiguous_rows": legacy_rows,
        "projection_loss_rows": projection_loss_rows,
        "violating_rows": violating_rows,
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
    operator_payload = _review_payload()
    operator_by_id = _operator_rows(operator_payload)
    review_ids = set(operator_by_id)
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        rows = _load_rows(conn, review_ids)
        conn.rollback()

    report = build_report(rows, operator_rows=operator_by_id)
    print(f"F4A_R4_BRONZE2E_CANDIDATE_COUNT={report['candidate_count']}")
    print(f"F4A_R4_BRONZE2E_OPERATOR_COUNT={report['operator_candidate_count']}")
    print(f"F4A_R4_BRONZE2E_REACHABLE={report['reachable_count']}")
    print(
        "F4A_R4_BRONZE2E_COVERAGE_RATIO="
        f"{report['reachable_without_extractor_gap_ratio']:.4f}"
    )
    print(f"F4A_R4_BRONZE2E_EXTRACTOR_GAP_ROWS={report['rows_with_extractor_gap']}")
    print(
        "F4A_R4_BRONZE2E_LEGACY_AMBIGUOUS_ROWS="
        + str(report["rows_with_legacy_ambiguous_status"])
    )
    print(
        "F4A_R4_BRONZE2E_PROJECTION_LOSS_ROWS="
        + str(report["rows_with_silver_to_operator_projection_loss"])
    )
    print(f"F4A_R4_BRONZE2E_VIOLATING_ROWS={report['violating_row_count']}")
    print(
        "F4A_R4_BRONZE2E_CONTEXT_OBSERVED="
        + json.dumps(report["context_observed_counts"], sort_keys=True)
    )
    print(
        "F4A_R4_BRONZE2E_GAP_FAMILIES="
        + json.dumps(report["extractor_gap_source_family_counts"], sort_keys=True)
    )
    print(
        "F4A_R4_BRONZE2E_COVERAGE_GATE="
        + ("PASS" if report["coverage_gate_pass"] else "FAIL")
    )

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
