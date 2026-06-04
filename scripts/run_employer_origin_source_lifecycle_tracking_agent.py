from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg
from src.search_intelligence.employer_origin_gate_registry import gate_order
from psycopg.rows import dict_row


SOURCE_LIFECYCLE_GATE = "source_lifecycle_tracking"


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: str
    dbname: str
    user: str
    password: str

    @classmethod
    def from_environment(cls) -> "DatabaseConfig":
        return cls(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
        )

    def dsn(self) -> str:
        return (
            f"host={self.host} "
            f"port={self.port} "
            f"dbname={self.dbname} "
            f"user={self.user} "
            f"password={self.password}"
        )


@dataclass(frozen=True)
class SourceCandidate:
    id: int
    company_key: str
    company_name: str
    source_name_candidate: str
    status: str
    risk_level: str


@dataclass(frozen=True)
class LifecycleMetrics:
    source_name: str
    raw_job_count: int
    silver_job_count: int
    ingestion_run_count: int
    latest_raw_fetched_at: str | None
    latest_ingestion_run_id: int | None


@dataclass(frozen=True)
class LifecycleOutcome:
    gate_status: str
    decision: str
    stop_reason: str | None
    evidence: dict[str, Any]


def build_lifecycle_outcome(
    candidate: SourceCandidate,
    metrics: LifecycleMetrics,
) -> LifecycleOutcome:
    evidence = {
        "lifecycle_agent": "s2y_employer_origin_source_lifecycle_tracking_agent",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_name": metrics.source_name,
        "candidate_status": candidate.status,
        "risk_level": candidate.risk_level,
        "raw_job_count": metrics.raw_job_count,
        "silver_job_count": metrics.silver_job_count,
        "ingestion_run_count": metrics.ingestion_run_count,
        "latest_raw_fetched_at": metrics.latest_raw_fetched_at,
        "latest_ingestion_run_id": metrics.latest_ingestion_run_id,
        "boundary": {
            "database_writes": True,
            "bronze_persistence": False,
            "connector_activation": False,
            "recurring_ingestion_activation": False,
            "csv_or_export_inputs_used": False,
        },
    }

    if metrics.raw_job_count > 0 and metrics.silver_job_count > 0:
        return LifecycleOutcome(
            gate_status="passed",
            decision="passed",
            stop_reason=None,
            evidence=evidence
            | {
                "interpretation": (
                    "Source has current raw and Silver evidence. Lifecycle tracking can remain active."
                )
            },
        )

    if metrics.raw_job_count > 0:
        return LifecycleOutcome(
            gate_status="manual_review_required",
            decision="manual_review_required",
            stop_reason="source has raw evidence but no Silver evidence",
            evidence=evidence
            | {
                "interpretation": (
                    "Source produces raw evidence, but no Silver-backed value is currently visible."
                )
            },
        )

    return LifecycleOutcome(
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason="source has no raw evidence",
        evidence=evidence
        | {
            "interpretation": (
                "Source has no current raw evidence. It should not be treated as an active value source."
            )
        },
    )


def lifecycle_report_lines(candidate: SourceCandidate, outcome: LifecycleOutcome) -> list[str]:
    evidence = outcome.evidence
    lines = [
        f"candidate_id: {candidate.id}",
        f"candidate: {candidate.company_key} | {candidate.source_name_candidate}",
        f"{SOURCE_LIFECYCLE_GATE}: {outcome.gate_status} / {outcome.decision}",
        f"raw_job_count: {evidence['raw_job_count']}",
        f"silver_job_count: {evidence['silver_job_count']}",
        f"ingestion_run_count: {evidence['ingestion_run_count']}",
    ]
    if outcome.stop_reason:
        lines.append(f"STOP: {outcome.stop_reason}")
    else:
        lines.append("NEXT: lifecycle gate is now tracked from DB evidence.")
    return lines


class LifecycleRepository:
    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def load_candidate(self, *, candidate_id: int | None, company_key: str | None) -> SourceCandidate:
        if candidate_id is None and not company_key:
            raise ValueError("Either candidate_id or company_key is required.")

        with self.conn.cursor(row_factory=dict_row) as cur:
            if candidate_id is not None:
                cur.execute(
                    """
                    select
                        id,
                        company_key,
                        company_name,
                        source_name_candidate,
                        status,
                        risk_level
                    from employer_origin_source_candidates
                    where id = %s
                    """,
                    (candidate_id,),
                )
            else:
                cur.execute(
                    """
                    select
                        id,
                        company_key,
                        company_name,
                        source_name_candidate,
                        status,
                        risk_level
                    from employer_origin_source_candidates
                    where company_key = %s
                    order by id desc
                    limit 1
                    """,
                    (company_key,),
                )
            row = cur.fetchone()

        if row is None:
            raise ValueError("No employer-origin source candidate found.")

        return SourceCandidate(
            id=int(row["id"]),
            company_key=str(row["company_key"]),
            company_name=str(row["company_name"]),
            source_name_candidate=str(row["source_name_candidate"]),
            status=str(row["status"]),
            risk_level=str(row["risk_level"]),
        )

    def load_metrics(self, source_name: str) -> LifecycleMetrics:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select
                    count(*)::int as raw_job_count,
                    max(fetched_at)::text as latest_raw_fetched_at
                from raw_jobs
                where source_name = %s
                """,
                (source_name,),
            )
            raw_row = cur.fetchone() or {}

            cur.execute(
                """
                select count(*)::int as silver_job_count
                from silver_jobs
                where source_name = %s
                """,
                (source_name,),
            )
            silver_row = cur.fetchone() or {}

            cur.execute(
                """
                select
                    count(*)::int as ingestion_run_count,
                    max(id)::int as latest_ingestion_run_id
                from ingestion_runs
                where source_name = %s
                """,
                (source_name,),
            )
            run_row = cur.fetchone() or {}

        return LifecycleMetrics(
            source_name=source_name,
            raw_job_count=int(raw_row.get("raw_job_count") or 0),
            silver_job_count=int(silver_row.get("silver_job_count") or 0),
            ingestion_run_count=int(run_row.get("ingestion_run_count") or 0),
            latest_raw_fetched_at=raw_row.get("latest_raw_fetched_at"),
            latest_ingestion_run_id=run_row.get("latest_ingestion_run_id"),
        )

    def record_lifecycle_gate(
        self,
        *,
        candidate_id: int,
        outcome: LifecycleOutcome,
        reviewed_by: str,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                insert into employer_origin_candidate_gate_reviews (
                    candidate_id,
                    gate_order,
                    gate_name,
                    gate_status,
                    decision,
                    stop_reason,
                    evidence,
                    reviewed_by
                )
                values (%s, 14, %s, %s, %s, %s, %s, %s)
                on conflict (candidate_id, gate_name)
                do update set
                    gate_status = excluded.gate_status,
                    decision = excluded.decision,
                    stop_reason = excluded.stop_reason,
                    evidence = excluded.evidence,
                    reviewed_by = excluded.reviewed_by
                """,
                (
                    candidate_id,
                    SOURCE_LIFECYCLE_GATE,
                    outcome.gate_status,
                    outcome.decision,
                    outcome.stop_reason,
                    json.dumps(outcome.evidence),
                    reviewed_by,
                ),
            )


def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        repo = LifecycleRepository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=args.company_key)
        metrics = repo.load_metrics(candidate.source_name_candidate)
        outcome = build_lifecycle_outcome(candidate, metrics)

        if not args.dry_run:
            repo.record_lifecycle_gate(
                candidate_id=candidate.id,
                outcome=outcome,
                reviewed_by=args.reviewed_by,
            )
            conn.commit()

    for line in lifecycle_report_lines(candidate, outcome):
        print(line)

    if args.dry_run:
        print("DRY RUN: no DB gate state was changed.")

    return 0 if outcome.gate_status == "passed" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DB-backed source lifecycle tracking gate agent for employer-origin sources."
    )

    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")

    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
