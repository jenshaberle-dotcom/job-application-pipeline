from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config


DECISION = "skipped"
REASON_PREFIX = "invalid_bronze:"


@dataclass(frozen=True)
class RequestedExpectation:
    raw_job_id: int
    expected_source_url: str


@dataclass(frozen=True)
class ObservedRow:
    raw_job_id: int
    source_name: str
    external_job_id: str
    source_url: str
    silver_job_id: int | None
    processing_decision: str | None
    processing_reason: str | None


@dataclass(frozen=True)
class PlannedRow:
    raw_job_id: int
    source_name: str
    source_url: str
    action: str


def full_reason(reason: str) -> str:
    normalized = reason.strip()
    if not normalized:
        raise ValueError("Quarantine reason must not be empty.")
    return f"{REASON_PREFIX}{normalized}"


def parse_expected_url(value: str) -> RequestedExpectation:
    raw_id, separator, url = value.partition("=")
    if not separator or not raw_id.strip().isdigit() or not url.strip():
        raise argparse.ArgumentTypeError(
            "--expected-url must use RAW_JOB_ID=EXACT_URL syntax."
        )
    return RequestedExpectation(
        raw_job_id=int(raw_id.strip()),
        expected_source_url=url.strip(),
    )


def normalize_expectations(
    raw_job_ids: list[int],
    expected_urls: list[RequestedExpectation],
) -> list[RequestedExpectation]:
    if not raw_job_ids:
        raise ValueError("At least one --raw-job-id is required.")
    if len(set(raw_job_ids)) != len(raw_job_ids):
        raise ValueError("Duplicate --raw-job-id values are not allowed.")

    by_id: dict[int, RequestedExpectation] = {}
    for expectation in expected_urls:
        if expectation.raw_job_id in by_id:
            raise ValueError(
                f"Duplicate --expected-url for raw_job_id={expectation.raw_job_id}."
            )
        by_id[expectation.raw_job_id] = expectation

    requested = set(raw_job_ids)
    expected = set(by_id)
    if requested != expected:
        missing_urls = sorted(requested - expected)
        unexpected_urls = sorted(expected - requested)
        raise ValueError(
            "Expected URLs must match requested raw-job IDs exactly. "
            f"missing_expected_urls={missing_urls} "
            f"unexpected_expected_urls={unexpected_urls}"
        )

    return [by_id[raw_job_id] for raw_job_id in raw_job_ids]


def build_quarantine_plan(
    *,
    expectations: list[RequestedExpectation],
    observed_rows: list[ObservedRow],
    expected_source: str,
    reason: str,
) -> list[PlannedRow]:
    expected_source = expected_source.strip()
    if not expected_source:
        raise ValueError("Expected source must not be empty.")

    reason_value = full_reason(reason)
    observed_by_id = {row.raw_job_id: row for row in observed_rows}
    requested_ids = [item.raw_job_id for item in expectations]

    if len(observed_by_id) != len(observed_rows):
        raise ValueError("Observed rows contain duplicate raw-job IDs.")

    missing = sorted(set(requested_ids) - set(observed_by_id))
    unexpected = sorted(set(observed_by_id) - set(requested_ids))
    if missing or unexpected:
        raise ValueError(
            "Observed rows do not match requested raw-job IDs exactly. "
            f"missing={missing} unexpected={unexpected}"
        )

    plan: list[PlannedRow] = []
    for expectation in expectations:
        row = observed_by_id[expectation.raw_job_id]

        if row.source_name != expected_source:
            raise ValueError(
                f"raw_job_id={row.raw_job_id} source mismatch: "
                f"expected={expected_source!r} actual={row.source_name!r}"
            )
        if row.source_url != expectation.expected_source_url:
            raise ValueError(
                f"raw_job_id={row.raw_job_id} URL mismatch: "
                f"expected={expectation.expected_source_url!r} "
                f"actual={row.source_url!r}"
            )
        if row.silver_job_id is not None:
            raise ValueError(
                f"raw_job_id={row.raw_job_id} already has "
                f"silver_job_id={row.silver_job_id}; "
                "quarantine refuses to rewrite downstream truth."
            )

        if row.processing_decision is not None:
            if (
                row.processing_decision == DECISION
                and row.processing_reason == reason_value
            ):
                action = "already_quarantined"
            else:
                raise ValueError(
                    f"raw_job_id={row.raw_job_id} has conflicting "
                    "processing decision: "
                    f"decision={row.processing_decision!r} "
                    f"reason={row.processing_reason!r}"
                )
        else:
            action = "insert_skipped_decision"

        plan.append(
            PlannedRow(
                raw_job_id=row.raw_job_id,
                source_name=row.source_name,
                source_url=row.source_url,
                action=action,
            )
        )

    return plan


def load_observed_rows(
    conn: psycopg.Connection[Any], raw_job_ids: list[int]
) -> list[ObservedRow]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                r.id AS raw_job_id,
                r.source_name,
                r.external_job_id,
                r.source_url,
                s.id AS silver_job_id,
                d.decision AS processing_decision,
                d.reason AS processing_reason
            FROM raw_jobs r
            LEFT JOIN silver_jobs s
                ON s.raw_job_id = r.id
            LEFT JOIN silver_processing_decisions d
                ON d.raw_job_id = r.id
            WHERE r.id = ANY(%s)
            ORDER BY r.id
            """,
            (raw_job_ids,),
        )
        rows = cur.fetchall()

    return [
        ObservedRow(
            raw_job_id=int(row["raw_job_id"]),
            source_name=str(row["source_name"]),
            external_job_id=str(row["external_job_id"] or ""),
            source_url=str(row["source_url"]),
            silver_job_id=(
                int(row["silver_job_id"])
                if row["silver_job_id"] is not None
                else None
            ),
            processing_decision=(
                str(row["processing_decision"])
                if row["processing_decision"] is not None
                else None
            ),
            processing_reason=(
                str(row["processing_reason"])
                if row["processing_reason"] is not None
                else None
            ),
        )
        for row in rows
    ]


def apply_quarantine(
    conn: psycopg.Connection[Any], *, plan: list[PlannedRow], reason: str
) -> int:
    reason_value = full_reason(reason)
    to_insert = [
        row.raw_job_id for row in plan if row.action == "insert_skipped_decision"
    ]
    if not to_insert:
        return 0

    inserted_count = 0
    with conn.cursor(row_factory=dict_row) as cur:
        for raw_job_id in to_insert:
            cur.execute(
                """
                INSERT INTO silver_processing_decisions (
                    raw_job_id,
                    decision,
                    reason,
                    role_matches,
                    skill_matches,
                    accessibility_matches
                )
                VALUES (%s, %s, %s, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb)
                ON CONFLICT (raw_job_id) DO NOTHING
                """,
                (raw_job_id, DECISION, reason_value),
            )
            inserted_count += cur.rowcount

        cur.execute(
            """
            SELECT raw_job_id, decision, reason
            FROM silver_processing_decisions
            WHERE raw_job_id = ANY(%s)
            ORDER BY raw_job_id
            """,
            ([row.raw_job_id for row in plan],),
        )
        verified = cur.fetchall()

    verified_by_id = {
        int(row["raw_job_id"]): (str(row["decision"]), str(row["reason"]))
        for row in verified
    }
    for row in plan:
        actual = verified_by_id.get(row.raw_job_id)
        if actual != (DECISION, reason_value):
            raise RuntimeError(
                "Post-apply verification failed for "
                f"raw_job_id={row.raw_job_id}: {actual!r}"
            )

    return inserted_count


def build_manifest(
    *,
    expectations: list[RequestedExpectation],
    observed_rows: list[ObservedRow],
    plan: list[PlannedRow],
    expected_source: str,
    reason: str,
    apply_requested: bool,
    inserted_count: int | None,
) -> dict[str, Any]:
    planned_inserts = sum(
        row.action == "insert_skipped_decision" for row in plan
    )
    already_quarantined = sum(
        row.action == "already_quarantined" for row in plan
    )

    if apply_requested:
        status = (
            "invalid_bronze_quarantine_applied"
            if inserted_count
            else "invalid_bronze_quarantine_already_satisfied"
        )
    else:
        status = (
            "invalid_bronze_quarantine_apply_ready"
            if planned_inserts
            else "invalid_bronze_quarantine_already_satisfied"
        )

    observed_by_id = {row.raw_job_id: row for row in observed_rows}
    return {
        "agent": "invalid_bronze_quarantine",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": status,
        "expected_source": expected_source,
        "reason": full_reason(reason),
        "apply_requested": apply_requested,
        "requested_rows": [
            {
                "raw_job_id": expectation.raw_job_id,
                "expected_source_url": expectation.expected_source_url,
                "actual_source_name": (
                    observed_by_id[expectation.raw_job_id].source_name
                ),
                "actual_source_url": (
                    observed_by_id[expectation.raw_job_id].source_url
                ),
                "existing_silver_job_id": (
                    observed_by_id[expectation.raw_job_id].silver_job_id
                ),
                "existing_processing_decision": (
                    observed_by_id[expectation.raw_job_id].processing_decision
                ),
                "existing_processing_reason": (
                    observed_by_id[expectation.raw_job_id].processing_reason
                ),
                "planned_action": next(
                    row.action
                    for row in plan
                    if row.raw_job_id == expectation.raw_job_id
                ),
            }
            for expectation in expectations
        ],
        "counts": {
            "requested": len(expectations),
            "planned_inserts": planned_inserts,
            "already_quarantined": already_quarantined,
            "inserted": inserted_count,
        },
        "boundary": {
            "raw_jobs_delete": False,
            "raw_jobs_update": False,
            "silver_jobs_mutation": False,
            "silver_processing_decision_insert": bool(
                apply_requested and planned_inserts
            ),
            "provider_calls": False,
            "scheduler_change": False,
            "recurring_ingestion_change": False,
            "ranking_mutation": False,
            "application_action": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dry-run-first quarantine for exact known-invalid Bronze raw jobs."
    )
    parser.add_argument("--raw-job-id", type=int, action="append", required=True)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument(
        "--expected-url",
        type=parse_expected_url,
        action="append",
        required=True,
        help="Repeat exact RAW_JOB_ID=SOURCE_URL expectations.",
    )
    parser.add_argument("--reason", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    expectations = normalize_expectations(args.raw_job_id, args.expected_url)

    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        observed_rows = load_observed_rows(
            conn, [item.raw_job_id for item in expectations]
        )
        plan = build_quarantine_plan(
            expectations=expectations,
            observed_rows=observed_rows,
            expected_source=args.expected_source,
            reason=args.reason,
        )

        inserted_count: int | None = None
        if args.apply:
            inserted_count = apply_quarantine(
                conn, plan=plan, reason=args.reason
            )
            conn.commit()
        else:
            conn.rollback()

    manifest = build_manifest(
        expectations=expectations,
        observed_rows=observed_rows,
        plan=plan,
        expected_source=args.expected_source,
        reason=args.reason,
        apply_requested=args.apply,
        inserted_count=inserted_count,
    )

    print("Invalid Bronze Quarantine")
    print(f"status: {manifest['status']}")
    print(f"requested: {manifest['counts']['requested']}")
    print(f"planned_inserts: {manifest['counts']['planned_inserts']}")
    print(f"apply_requested: {args.apply}")
    if args.print_json:
        print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
