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
from src.ingestion.eon_controlled_pilot import (
    EXPECTED_EXTERNAL_JOB_ID,
    EXPECTED_TITLE,
    PILOT_SOURCE_NAME,
    is_authorized_pilot_raw_data,
)
from src.search_intelligence.eon_product_v1_assessment import (
    EXPECTED_CANONICAL_SOURCE_TYPE,
)
from src.search_intelligence.eon_product_v1_source_evidence import (
    APPROVAL_TOKEN,
    ASSESSMENT_COLUMNS,
    DEFAULT_ASSESSED_BY,
    EXPECTED_HARD_FILTER_STATUS,
    EXPECTED_READINESS,
    REFRESH_KEY,
    AssessmentRefresh,
    assessment_is_refreshed,
    build_eon_assessment_refresh,
    canonical_assessment_payload,
)


EXPECTED_RAW_JOB_ID = 26342
EXPECTED_SILVER_JOB_ID = 466
REPORT_SCHEMA = "eon_product_v1_source_evidence_refresh_execution.v1"
REVISION_TABLE = "job_product_assessment_revisions"


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


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def ensure_revision_schema(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) AS relation", (f"public.{REVISION_TABLE}",))
        row = cur.fetchone()
    if row is None or row["relation"] is None:
        raise RuntimeError(
            "job_product_assessment_revisions is missing; apply tracked migration "
            "087_create_job_product_assessment_revisions.sql first"
        )


def load_binding(
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
    row = rows[0]
    if raw_job_id != EXPECTED_RAW_JOB_ID or silver_job_id != EXPECTED_SILVER_JOB_ID:
        raise ValueError("runner is bound to the exact E.ON pilot IDs")
    if row["source_name"] != PILOT_SOURCE_NAME:
        raise ValueError("E.ON source mismatch")
    if row["external_job_id"] != EXPECTED_EXTERNAL_JOB_ID:
        raise ValueError("E.ON external job ID mismatch")
    if row["title"] != EXPECTED_TITLE:
        raise ValueError("E.ON title mismatch")
    if row["canonical_source_type"] != EXPECTED_CANONICAL_SOURCE_TYPE:
        raise ValueError("E.ON canonical source type mismatch")
    if not is_authorized_pilot_raw_data(row["raw_data"]):
        raise ValueError("raw job is not the authorized E.ON pilot dataset")
    return row


def load_assessment(
    conn: psycopg.Connection[Any],
    *,
    silver_job_id: int,
    lock: bool = False,
) -> Mapping[str, Any]:
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
        row = cur.fetchone()
    if row is None:
        raise ValueError("persisted E.ON Product V1 assessment is missing")
    return row


def load_revision(
    conn: psycopg.Connection[Any],
    *,
    silver_job_id: int,
    lock: bool = False,
) -> Mapping[str, Any] | None:
    lock_clause = "FOR UPDATE" if lock else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                id,
                silver_job_id,
                revision_key,
                previous_payload,
                next_payload,
                source_evidence,
                applied_by,
                applied_at
            FROM job_product_assessment_revisions
            WHERE silver_job_id = %s
              AND revision_key = %s
            {lock_clause}
            """,
            (silver_job_id, REFRESH_KEY),
        )
        return cur.fetchone()


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
) -> Mapping[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM gold_product_v1_hard_filter_evaluation
            WHERE silver_job_id = %s
            """,
            (silver_job_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError("Product V1 hard-filter evaluation is missing")
    return row


def _payloads_match(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return _json_safe(left) == _json_safe(right)


def validate_revision(
    revision: Mapping[str, Any],
    *,
    refresh: AssessmentRefresh,
    current_payload: Mapping[str, Any],
) -> None:
    if revision["revision_key"] != REFRESH_KEY:
        raise RuntimeError("assessment revision key mismatch")
    if int(revision["silver_job_id"]) != EXPECTED_SILVER_JOB_ID:
        raise RuntimeError("assessment revision Silver binding mismatch")
    if not _payloads_match(revision["next_payload"], current_payload):
        raise RuntimeError("assessment revision next payload does not match current state")
    if not _payloads_match(
        revision["source_evidence"],
        refresh.source_evidence.canonical_payload(),
    ):
        raise RuntimeError("assessment revision source evidence mismatch")


def validate_post_state(
    *,
    assessment: Mapping[str, Any],
    readiness: Mapping[str, Any],
    hard_filter: Mapping[str, Any],
) -> None:
    _require(assessment_is_refreshed(assessment), "assessment refresh is incomplete")
    _require(
        assessment["hard_filter_status"] == EXPECTED_HARD_FILTER_STATUS,
        "direct hard-filter status changed unexpectedly",
    )
    _require(
        readiness["product_readiness_status"] == EXPECTED_READINESS,
        "Product V1 readiness changed unexpectedly",
    )
    _require(
        readiness["hard_filter_status"] == EXPECTED_HARD_FILTER_STATUS,
        "derived readiness hard-filter status changed unexpectedly",
    )
    _require(hard_filter["employment_status"] == "passed", "employment hard filter did not pass")
    _require(hard_filter["language_status"] == "passed", "language hard filter did not pass")
    _require(
        hard_filter["weekly_hours_status"] == "manual_review_required",
        "weekly-hours evidence was not preserved as manual review",
    )
    _require(
        hard_filter["seniority_status"] == "manual_review_required",
        "seniority/capability evidence was not preserved as manual review",
    )
    _require(
        hard_filter["hard_filter_status"] == EXPECTED_HARD_FILTER_STATUS,
        "overall hard-filter result changed unexpectedly",
    )
    for column in (
        "profile_direction_score",
        "data_focus_score",
        "reliability_focus_score",
        "evidence_quality_score",
        "overall_quality_score",
    ):
        _require(readiness[column] is None, f"unexpected ranking score: {column}")


def insert_revision(
    conn: psycopg.Connection[Any],
    *,
    refresh: AssessmentRefresh,
    applied_by: str,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO job_product_assessment_revisions (
                silver_job_id,
                revision_key,
                previous_payload,
                next_payload,
                source_evidence,
                applied_by
            )
            VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
            RETURNING id
            """,
            (
                EXPECTED_SILVER_JOB_ID,
                REFRESH_KEY,
                json.dumps(_json_safe(refresh.previous_payload), sort_keys=True),
                json.dumps(_json_safe(refresh.next_payload), sort_keys=True),
                json.dumps(
                    _json_safe(refresh.source_evidence.canonical_payload()),
                    sort_keys=True,
                ),
                applied_by,
            ),
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("assessment revision insert returned no id")
    return int(row["id"])


def update_assessment(
    conn: psycopg.Connection[Any],
    *,
    refresh: AssessmentRefresh,
) -> None:
    payload = refresh.next_payload
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE job_product_assessments
            SET
                work_model = %(work_model)s,
                explanations = %(explanations)s::jsonb,
                uncertainties = %(uncertainties)s::jsonb,
                assessed_by = %(assessed_by)s,
                required_languages = %(required_languages)s::jsonb,
                language_evidence_status = %(language_evidence_status)s,
                requirements_seniority = %(requirements_seniority)s,
                seniority_evidence_status = %(seniority_evidence_status)s,
                updated_at = NOW()
            WHERE silver_job_id = %(silver_job_id)s
            """,
            {
                "silver_job_id": EXPECTED_SILVER_JOB_ID,
                "work_model": payload["work_model"],
                "explanations": json.dumps(
                    _json_safe(payload["explanations"]),
                    sort_keys=True,
                ),
                "uncertainties": json.dumps(
                    _json_safe(payload["uncertainties"]),
                    sort_keys=True,
                ),
                "assessed_by": payload["assessed_by"],
                "required_languages": json.dumps(payload["required_languages"]),
                "language_evidence_status": payload["language_evidence_status"],
                "requirements_seniority": payload["requirements_seniority"],
                "seniority_evidence_status": payload["seniority_evidence_status"],
            },
        )
        if cur.rowcount != 1:
            raise RuntimeError("assessment refresh did not update exactly one row")


def apply_refresh(
    *,
    raw_job_id: int,
    silver_job_id: int,
    applied_by: str,
    expected_refresh: AssessmentRefresh,
) -> tuple[bool, bool, Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    conn = connect()
    try:
        with conn.transaction():
            ensure_revision_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"{REFRESH_KEY}:{silver_job_id}",),
                )

            binding = load_binding(
                conn,
                raw_job_id=raw_job_id,
                silver_job_id=silver_job_id,
                lock=True,
            )
            current = load_assessment(conn, silver_job_id=silver_job_id, lock=True)
            current_payload = canonical_assessment_payload(current)
            rebuilt = build_eon_assessment_refresh(
                existing_assessment=current,
                raw_data=binding["raw_data"],
                assessed_by=applied_by,
            )
            if not _payloads_match(
                rebuilt.next_payload,
                expected_refresh.next_payload,
            ) or not _payloads_match(
                rebuilt.source_evidence.canonical_payload(),
                expected_refresh.source_evidence.canonical_payload(),
            ):
                raise RuntimeError("source evidence refresh changed between preflight and Apply")

            revision = load_revision(conn, silver_job_id=silver_job_id, lock=True)
            already_refreshed = assessment_is_refreshed(current_payload)
            revision_inserted = False
            assessment_updated = False

            if already_refreshed:
                if revision is None:
                    raise RuntimeError("refreshed assessment is missing its audit revision")
                validate_revision(
                    revision,
                    refresh=rebuilt,
                    current_payload=current_payload,
                )
            else:
                if revision is not None:
                    raise RuntimeError("assessment revision exists before assessment refresh")
                if not rebuilt.changed_fields:
                    raise RuntimeError("assessment refresh produced no bounded changes")
                insert_revision(conn, refresh=rebuilt, applied_by=applied_by)
                revision_inserted = True
                update_assessment(conn, refresh=rebuilt)
                assessment_updated = True

            after = load_assessment(conn, silver_job_id=silver_job_id)
            after_payload = canonical_assessment_payload(after)
            if not _payloads_match(after_payload, rebuilt.next_payload):
                raise RuntimeError("persisted assessment does not match refreshed payload")

            stored_revision = load_revision(conn, silver_job_id=silver_job_id)
            if stored_revision is None:
                raise RuntimeError("assessment refresh revision was not persisted")
            validate_revision(
                stored_revision,
                refresh=rebuilt,
                current_payload=after_payload,
            )

            readiness = load_readiness(conn, silver_job_id=silver_job_id)
            hard_filter = load_hard_filter_evaluation(conn, silver_job_id=silver_job_id)
            validate_post_state(
                assessment=after,
                readiness=readiness,
                hard_filter=hard_filter,
            )

        return (
            revision_inserted,
            assessment_updated,
            after,
            readiness,
            hard_filter,
        )
    finally:
        conn.close()


def write_report(
    *,
    output_dir: Path,
    mode: str,
    refresh: AssessmentRefresh,
    revision_present_before: bool,
    revision_inserted: bool,
    assessment_updated: bool,
    readiness_before: Mapping[str, Any],
    readiness_after: Mapping[str, Any] | None,
    hard_filter_after: Mapping[str, Any] | None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_dir / f"eon_product_v1_source_evidence_refresh_{stamp}.json"
    payload = {
        "schema_version": REPORT_SCHEMA,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "mode": mode,
        "refresh_key": REFRESH_KEY,
        "raw_job_id": EXPECTED_RAW_JOB_ID,
        "silver_job_id": EXPECTED_SILVER_JOB_ID,
        "changed_fields": list(refresh.changed_fields),
        "source_evidence": _json_safe(refresh.source_evidence.canonical_payload()),
        "previous_assessment": _json_safe(refresh.previous_payload),
        "proposed_assessment": _json_safe(refresh.next_payload),
        "revision_present_before": revision_present_before,
        "revision_inserted": revision_inserted,
        "assessment_updated": assessment_updated,
        "readiness_before": _json_safe(readiness_before),
        "readiness_after": _json_safe(readiness_after) if readiness_after else None,
        "hard_filter_after": _json_safe(hard_filter_after) if hard_filter_after else None,
        "remaining_required_evidence": ["weekly_hours", "capability_fit"],
        "review_output_only_not_pipeline_input": True,
        "boundary": {
            "network_requests": 0,
            "provider_requests": 0,
            "scheduler_changed": False,
            "connector_activated": False,
            "bronze_rows_created": 0,
            "silver_rows_created": 0,
            "location_rows_changed": 0,
            "assessment_rows_updated_max": 1,
            "assessment_revision_rows_inserted_max": 1,
            "ranking_scores_created": False,
            "hard_filter_pass_forced": False,
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
        description=(
            "Refresh the exact E.ON Product V1 assessment from already stored "
            "employer-origin evidence."
        )
    )
    parser.add_argument("--raw-job-id", type=int, required=True)
    parser.add_argument("--silver-job-id", type=int, required=True)
    parser.add_argument("--applied-by", default=DEFAULT_ASSESSED_BY)
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
    applied_by = args.applied_by.strip()
    if not applied_by:
        raise SystemExit("--applied-by must not be blank")
    if args.raw_job_id != EXPECTED_RAW_JOB_ID or args.silver_job_id != EXPECTED_SILVER_JOB_ID:
        raise SystemExit("runner is bound to raw job 26342 and Silver job 466")
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit(f"--apply requires --approval-token {APPROVAL_TOKEN}")
    if not args.apply and args.approval_token:
        raise SystemExit("--approval-token is accepted only together with --apply")

    try:
        conn = connect()
        try:
            ensure_revision_schema(conn)
            binding = load_binding(
                conn,
                raw_job_id=args.raw_job_id,
                silver_job_id=args.silver_job_id,
            )
            existing = load_assessment(conn, silver_job_id=args.silver_job_id)
            refresh = build_eon_assessment_refresh(
                existing_assessment=existing,
                raw_data=binding["raw_data"],
                assessed_by=applied_by,
            )
            revision = load_revision(conn, silver_job_id=args.silver_job_id)
            readiness_before = load_readiness(conn, silver_job_id=args.silver_job_id)
            current_payload = canonical_assessment_payload(existing)
            current_is_refreshed = assessment_is_refreshed(current_payload)
            if current_is_refreshed:
                if revision is None:
                    raise RuntimeError("refreshed assessment is missing its audit revision")
                validate_revision(
                    revision,
                    refresh=refresh,
                    current_payload=current_payload,
                )
            elif revision is not None:
                raise RuntimeError("assessment revision exists before assessment refresh")
            conn.rollback()
        finally:
            conn.close()

        revision_inserted = False
        assessment_updated = False
        readiness_after: Mapping[str, Any] | None = None
        hard_filter_after: Mapping[str, Any] | None = None
        if args.apply:
            (
                revision_inserted,
                assessment_updated,
                _after,
                readiness_after,
                hard_filter_after,
            ) = apply_refresh(
                raw_job_id=args.raw_job_id,
                silver_job_id=args.silver_job_id,
                applied_by=applied_by,
                expected_refresh=refresh,
            )

        report_path = write_report(
            output_dir=args.output_dir,
            mode="apply" if args.apply else "plan_only",
            refresh=refresh,
            revision_present_before=revision is not None,
            revision_inserted=revision_inserted,
            assessment_updated=assessment_updated,
            readiness_before=readiness_before,
            readiness_after=readiness_after,
            hard_filter_after=hard_filter_after,
        )
    except (OSError, ValueError, RuntimeError, psycopg.Error) as exc:
        raise SystemExit(str(exc)) from exc

    print("E.ON Product V1 source evidence refresh")
    print(f"mode: {'apply' if args.apply else 'plan_only'}")
    print(f"raw_job_id: {args.raw_job_id}")
    print(f"silver_job_id: {args.silver_job_id}")
    print("required_languages: de, en")
    print("language_evidence_status: observed")
    print("work_model: hybrid")
    print("requirements_seniority: senior")
    print("seniority_evidence_status: observed")
    print("weekly_hours_evidence_status: unknown")
    print("capability_fit_status: unknown")
    print(f"revision_inserted: {revision_inserted}")
    print(f"assessment_updated: {assessment_updated}")
    if readiness_after is not None:
        print(f"readiness_after: {readiness_after['product_readiness_status']}")
    print("remaining_required_evidence: weekly_hours, capability_fit")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
