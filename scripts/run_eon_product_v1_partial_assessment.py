from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.eon_product_v1_assessment import (
    APPROVAL_TOKEN,
    ASSESSMENT_KEY,
    DEFAULT_ASSESSED_BY,
    EXPECTED_POST_ASSESSMENT_STATUS,
    PartialProductAssessment,
    bind_eon_job,
    build_partial_assessment,
)

REPORT_SCHEMA = "eon_product_v1_partial_assessment_execution.v1"

ASSESSMENT_COLUMNS = (
    "silver_job_id",
    "origin_validation_status",
    "activity_status",
    "hard_filter_status",
    "profile_direction_score",
    "data_focus_score",
    "reliability_focus_score",
    "evidence_quality_score",
    "overall_quality_score",
    "work_model",
    "commute_minutes",
    "public_transport_quality",
    "ranking_factors",
    "explanations",
    "uncertainties",
    "policy_key",
    "policy_version",
    "assessed_by",
    "employment_type",
    "employment_evidence_status",
    "required_languages",
    "language_evidence_status",
    "weekly_hours_min",
    "weekly_hours_max",
    "weekly_hours_evidence_status",
    "salary_min_gross_eur",
    "salary_max_gross_eur",
    "salary_evidence_status",
    "title_seniority",
    "requirements_seniority",
    "capability_fit_status",
    "seniority_evidence_status",
)


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def load_job_row(
    conn: psycopg.Connection[Any],
    *,
    raw_job_id: int,
    silver_job_id: int,
    lock: bool = False,
) -> Mapping[str, Any]:
    lock_clause = "FOR SHARE OF r, s" if lock else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                r.id AS raw_job_id,
                s.id AS silver_job_id,
                r.source_name,
                r.external_job_id,
                r.raw_data,
                s.title,
                s.canonical_source_type
            FROM raw_jobs r
            JOIN silver_jobs s
              ON s.raw_job_id = r.id
            WHERE r.id = %s
              AND s.id = %s
            {lock_clause}
            """,
            (raw_job_id, silver_job_id),
        )
        rows = cur.fetchall()
    if len(rows) != 1:
        raise ValueError(
            "expected exactly one joined raw/Silver E.ON job, "
            f"found {len(rows)}"
        )
    return rows[0]


def load_policies(
    conn: psycopg.Connection[Any],
    *,
    lock: bool = False,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    lock_clause = "FOR SHARE" if lock else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT *
            FROM product_v1_ranking_policy
            WHERE policy_key = 'default'
            {lock_clause}
            """
        )
        ranking = cur.fetchone()
        cur.execute(
            f"""
            SELECT *
            FROM product_v1_hard_filter_policy
            WHERE policy_key = 'default'
            {lock_clause}
            """
        )
        hard_filter = cur.fetchone()
    if ranking is None or hard_filter is None:
        raise ValueError("approved Product V1 policies are missing")
    return ranking, hard_filter


def load_readiness(
    conn: psycopg.Connection[Any],
    *,
    silver_job_id: int,
) -> Mapping[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM gold_product_v1_job_readiness
            WHERE silver_job_id = %s
            """,
            (silver_job_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError("Product V1 readiness row is missing")
    return row


def load_hard_filter_evaluation(
    conn: psycopg.Connection[Any],
    *,
    silver_job_id: int,
) -> Mapping[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM gold_product_v1_hard_filter_evaluation
            WHERE silver_job_id = %s
            """,
            (silver_job_id,),
        )
        return cur.fetchone()


def load_existing_assessment(
    conn: psycopg.Connection[Any],
    *,
    silver_job_id: int,
    lock: bool = False,
) -> Mapping[str, Any] | None:
    lock_clause = "FOR UPDATE" if lock else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {', '.join(ASSESSMENT_COLUMNS)}
            FROM job_product_assessments
            WHERE silver_job_id = %s
            {lock_clause}
            """,
            (silver_job_id,),
        )
        return cur.fetchone()


def _canonical_existing(row: Mapping[str, Any]) -> dict[str, Any]:
    return {column: _json_safe(row.get(column)) for column in ASSESSMENT_COLUMNS}


def assessment_matches(
    existing: Mapping[str, Any],
    assessment: PartialProductAssessment,
) -> bool:
    return _canonical_existing(existing) == _json_safe(assessment.canonical_payload())


def insert_assessment(
    conn: psycopg.Connection[Any],
    *,
    assessment: PartialProductAssessment,
) -> None:
    payload = assessment.canonical_payload()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO job_product_assessments (
                silver_job_id,
                origin_validation_status,
                activity_status,
                hard_filter_status,
                profile_direction_score,
                data_focus_score,
                reliability_focus_score,
                evidence_quality_score,
                overall_quality_score,
                work_model,
                commute_minutes,
                public_transport_quality,
                ranking_factors,
                explanations,
                uncertainties,
                policy_key,
                policy_version,
                assessed_by,
                employment_type,
                employment_evidence_status,
                required_languages,
                language_evidence_status,
                weekly_hours_min,
                weekly_hours_max,
                weekly_hours_evidence_status,
                salary_min_gross_eur,
                salary_max_gross_eur,
                salary_evidence_status,
                title_seniority,
                requirements_seniority,
                capability_fit_status,
                seniority_evidence_status
            )
            VALUES (
                %(silver_job_id)s,
                %(origin_validation_status)s,
                %(activity_status)s,
                %(hard_filter_status)s,
                %(profile_direction_score)s,
                %(data_focus_score)s,
                %(reliability_focus_score)s,
                %(evidence_quality_score)s,
                %(overall_quality_score)s,
                %(work_model)s,
                %(commute_minutes)s,
                %(public_transport_quality)s,
                %(ranking_factors)s::jsonb,
                %(explanations)s::jsonb,
                %(uncertainties)s::jsonb,
                %(policy_key)s,
                %(policy_version)s,
                %(assessed_by)s,
                %(employment_type)s,
                %(employment_evidence_status)s,
                %(required_languages)s::jsonb,
                %(language_evidence_status)s,
                %(weekly_hours_min)s,
                %(weekly_hours_max)s,
                %(weekly_hours_evidence_status)s,
                %(salary_min_gross_eur)s,
                %(salary_max_gross_eur)s,
                %(salary_evidence_status)s,
                %(title_seniority)s,
                %(requirements_seniority)s,
                %(capability_fit_status)s,
                %(seniority_evidence_status)s
            )
            """,
            {
                **payload,
                "ranking_factors": json.dumps(payload["ranking_factors"], sort_keys=True),
                "explanations": json.dumps(payload["explanations"], sort_keys=True),
                "uncertainties": json.dumps(payload["uncertainties"], sort_keys=True),
                "required_languages": json.dumps(payload["required_languages"], sort_keys=True),
            },
        )
        if cur.rowcount != 1:
            raise RuntimeError("partial Product V1 assessment insert did not write one row")


def validate_score_boundary(readiness: Mapping[str, Any]) -> None:
    for key in (
        "profile_direction_score",
        "data_focus_score",
        "reliability_focus_score",
        "evidence_quality_score",
        "overall_quality_score",
    ):
        if readiness.get(key) is not None:
            raise RuntimeError(f"unexpected fabricated assessment score: {key}")


def apply_partial_assessment(
    *,
    raw_job_id: int,
    silver_job_id: int,
    assessed_by: str,
    expected: PartialProductAssessment,
) -> tuple[bool, Mapping[str, Any], Mapping[str, Any] | None]:
    conn = connect()
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"{ASSESSMENT_KEY}:{silver_job_id}",),
                )
            row = load_job_row(
                conn,
                raw_job_id=raw_job_id,
                silver_job_id=silver_job_id,
                lock=True,
            )
            ranking, hard_filter = load_policies(conn, lock=True)
            binding = bind_eon_job(
                row=row,
                expected_raw_job_id=raw_job_id,
                expected_silver_job_id=silver_job_id,
            )
            rebuilt = build_partial_assessment(
                binding=binding,
                ranking_policy=ranking,
                hard_filter_policy=hard_filter,
                assessed_by=assessed_by,
            )
            if rebuilt.canonical_payload() != expected.canonical_payload():
                raise RuntimeError("assessment changed between preflight and Apply")

            existing = load_existing_assessment(
                conn,
                silver_job_id=silver_job_id,
                lock=True,
            )
            inserted = existing is None
            if existing is None:
                insert_assessment(conn, assessment=rebuilt)
            elif not assessment_matches(existing, rebuilt):
                raise RuntimeError("conflicting Product V1 assessment already exists")

            readiness = load_readiness(conn, silver_job_id=silver_job_id)
            validate_score_boundary(readiness)
            status = str(readiness["product_readiness_status"])
            if status != EXPECTED_POST_ASSESSMENT_STATUS:
                raise RuntimeError(
                    "unexpected post-assessment readiness: "
                    f"expected={EXPECTED_POST_ASSESSMENT_STATUS} actual={status}"
                )
            hard_filter_evaluation = load_hard_filter_evaluation(
                conn,
                silver_job_id=silver_job_id,
            )
        return inserted, readiness, hard_filter_evaluation
    finally:
        conn.close()


def write_report(
    *,
    output_dir: Path,
    mode: str,
    raw_job_id: int,
    silver_job_id: int,
    readiness_before: Mapping[str, Any],
    assessment: PartialProductAssessment,
    existing_assessment: Mapping[str, Any] | None,
    assessment_inserted: bool,
    readiness_after: Mapping[str, Any] | None,
    hard_filter_evaluation: Mapping[str, Any] | None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_dir / f"eon_product_v1_partial_assessment_{stamp}.json"
    payload = {
        "schema_version": REPORT_SCHEMA,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "mode": mode,
        "assessment_key": ASSESSMENT_KEY,
        "raw_job_id": raw_job_id,
        "silver_job_id": silver_job_id,
        "readiness_before": _json_safe(readiness_before),
        "proposed_assessment": _json_safe(assessment.canonical_payload()),
        "existing_assessment_present": existing_assessment is not None,
        "existing_assessment_matches": (
            assessment_matches(existing_assessment, assessment)
            if existing_assessment is not None
            else None
        ),
        "assessment_inserted": assessment_inserted,
        "readiness_after": _json_safe(readiness_after) if readiness_after else None,
        "hard_filter_evaluation": (
            _json_safe(hard_filter_evaluation) if hard_filter_evaluation else None
        ),
        "review_output_only_not_pipeline_input": True,
        "boundary": {
            "network_requests": 0,
            "provider_requests": 0,
            "scheduler_changed": False,
            "connector_activated": False,
            "bronze_rows_created": 0,
            "silver_rows_created": 0,
            "assessment_rows_max": 1,
            "ranking_scores_created": False,
            "top_jobs_forced": False,
            "application_action_performed": False,
            "exact_eon_pilot_job_only": True,
        },
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist one source-grounded partial Product V1 assessment for the exact E.ON pilot job."
    )
    parser.add_argument("--raw-job-id", type=int, required=True)
    parser.add_argument("--silver-job-id", type=int, required=True)
    parser.add_argument("--assessed-by", default=DEFAULT_ASSESSED_BY)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    assessed_by = args.assessed_by.strip()
    if not assessed_by:
        raise SystemExit("--assessed-by must not be blank")
    if args.raw_job_id <= 0 or args.silver_job_id <= 0:
        raise SystemExit("raw and Silver job IDs must be positive")
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit(f"--apply requires --approval-token {APPROVAL_TOKEN}")
    if not args.apply and args.approval_token:
        raise SystemExit("--approval-token is accepted only together with --apply")

    try:
        conn = connect()
        try:
            row = load_job_row(
                conn,
                raw_job_id=args.raw_job_id,
                silver_job_id=args.silver_job_id,
            )
            ranking, hard_filter = load_policies(conn)
            binding = bind_eon_job(
                row=row,
                expected_raw_job_id=args.raw_job_id,
                expected_silver_job_id=args.silver_job_id,
            )
            assessment = build_partial_assessment(
                binding=binding,
                ranking_policy=ranking,
                hard_filter_policy=hard_filter,
                assessed_by=assessed_by,
            )
            readiness_before = load_readiness(conn, silver_job_id=args.silver_job_id)
            existing = load_existing_assessment(
                conn,
                silver_job_id=args.silver_job_id,
            )
            if existing is not None and not assessment_matches(existing, assessment):
                raise RuntimeError("conflicting Product V1 assessment already exists")
            conn.rollback()
        finally:
            conn.close()

        inserted = False
        readiness_after: Mapping[str, Any] | None = None
        hard_filter_evaluation: Mapping[str, Any] | None = None
        if args.apply:
            inserted, readiness_after, hard_filter_evaluation = apply_partial_assessment(
                raw_job_id=args.raw_job_id,
                silver_job_id=args.silver_job_id,
                assessed_by=assessed_by,
                expected=assessment,
            )

        report_path = write_report(
            output_dir=args.output_dir,
            mode="apply" if args.apply else "plan_only",
            raw_job_id=args.raw_job_id,
            silver_job_id=args.silver_job_id,
            readiness_before=readiness_before,
            assessment=assessment,
            existing_assessment=existing,
            assessment_inserted=inserted,
            readiness_after=readiness_after,
            hard_filter_evaluation=hard_filter_evaluation,
        )
    except (OSError, ValueError, RuntimeError, psycopg.Error) as exc:
        raise SystemExit(str(exc)) from exc

    print("E.ON Product V1 partial assessment")
    print(f"mode: {'apply' if args.apply else 'plan_only'}")
    print(f"raw_job_id: {args.raw_job_id}")
    print(f"silver_job_id: {args.silver_job_id}")
    print(f"readiness_before: {readiness_before['product_readiness_status']}")
    print(f"assessment_inserted: {str(inserted).lower()}")
    if readiness_after is not None:
        print(f"readiness_after: {readiness_after['product_readiness_status']}")
        print("STOP: missing hard-filter and capability evidence remains manual-review-required.")
    else:
        print("network_requests: 0")
        print("database_mutation: false")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
