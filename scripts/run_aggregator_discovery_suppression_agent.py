"""DB-backed aggregator discovery suppression preview.

This agent reads known employer-origin candidates from PostgreSQL and compares them
with current aggregator-origin Silver company signals. It does not call external
websites and does not use exports as process inputs.

By default, the agent is read-only. With ``--write-snapshot`` it persists a review
snapshot to dedicated aggregator-discovery review-state tables. This is still not a
Bronze write, source activation or scheduler change.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.aggregator_discovery_policy import (
    AggregatorCompanySignal,
    AggregatorSuppressionDecision,
    KnownEmployerCandidate,
    suppress_aggregator_signal,
)


DEFAULT_AGGREGATOR_SOURCES = ("stepstone",)
DECISION_SCOPE = "stepstone_known_candidate_suppression"


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


class SuppressionRepository:
    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def load_known_candidates(self) -> list[KnownEmployerCandidate]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                with latest_gate as (
                    select distinct on (g.candidate_id)
                        g.candidate_id,
                        g.gate_name,
                        g.gate_status,
                        g.stop_reason,
                        g.reviewed_at::text as reviewed_at
                    from employer_origin_candidate_gate_reviews g
                    order by g.candidate_id, g.gate_order desc, g.updated_at desc, g.id desc
                )
                select
                    c.id as candidate_id,
                    c.company_key,
                    c.company_name,
                    c.source_name_candidate,
                    c.source_family_candidate,
                    c.status,
                    c.risk_level,
                    lg.gate_name as latest_gate_name,
                    lg.gate_status as latest_gate_status,
                    lg.stop_reason as latest_stop_reason,
                    lg.reviewed_at as latest_reviewed_at
                from employer_origin_source_candidates c
                left join latest_gate lg
                    on lg.candidate_id = c.id
                order by c.company_key, c.id
                """
            )
            rows = cur.fetchall()

        return [
            KnownEmployerCandidate(
                candidate_id=int(row["candidate_id"]),
                company_key=str(row["company_key"]),
                company_name=str(row["company_name"]),
                source_name_candidate=str(row["source_name_candidate"]),
                source_family_candidate=str(row["source_family_candidate"]),
                status=str(row["status"]),
                risk_level=str(row["risk_level"]),
                latest_gate_name=row["latest_gate_name"],
                latest_gate_status=row["latest_gate_status"],
                latest_stop_reason=row["latest_stop_reason"],
                latest_reviewed_at=row["latest_reviewed_at"],
            )
            for row in rows
        ]

    def load_aggregator_company_signals(
        self,
        sources: tuple[str, ...],
    ) -> list[AggregatorCompanySignal]:
        if not sources:
            return []

        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select
                    source_name,
                    normalized_company_name,
                    count(*)::int as silver_job_count,
                    min(coalesce(normalized_at, created_at))::text as first_seen_at,
                    max(coalesce(normalized_at, created_at))::text as last_seen_at
                from silver_jobs
                where source_name = any(%s)
                    and normalized_company_name is not null
                    and btrim(normalized_company_name) <> ''
                group by source_name, normalized_company_name
                order by source_name, normalized_company_name
                """,
                (list(sources),),
            )
            rows = cur.fetchall()

        return [
            AggregatorCompanySignal(
                source_name=str(row["source_name"]),
                company=str(row["normalized_company_name"]),
                silver_job_count=int(row["silver_job_count"]),
                first_seen_at=row["first_seen_at"],
                last_seen_at=row["last_seen_at"],
            )
            for row in rows
        ]

    def load_aggregator_companies(self, sources: tuple[str, ...]) -> list[str]:
        """Compatibility helper for older call sites/tests."""
        return [
            signal.company
            for signal in self.load_aggregator_company_signals(sources)
        ]

    def write_snapshot(
        self,
        *,
        decisions: list[AggregatorSuppressionDecision],
        aggregator_sources: tuple[str, ...],
        reviewed_by: str,
    ) -> int:
        summary = decision_summary(decisions)
        evidence = {
            "aggregator_sources": list(aggregator_sources),
            "boundary": {
                "reads_silver_jobs": True,
                "reads_employer_origin_candidates": True,
                "external_http_calls": False,
                "bronze_writes": False,
                "source_activation": False,
                "scheduler_changes": False,
                "export_as_input": False,
            },
            "summary": summary,
        }

        with self.conn.cursor() as cur:
            cur.execute(
                """
                insert into aggregator_discovery_suppression_batches (
                    decision_scope,
                    aggregator_sources,
                    company_count,
                    suppressed_count,
                    kept_for_discovery_review_count,
                    recheck_eligible_known_candidate_count,
                    reviewed_by,
                    evidence
                ) values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                returning id
                """,
                (
                    DECISION_SCOPE,
                    list(aggregator_sources),
                    summary["company_count"],
                    summary["suppressed_count"],
                    summary["kept_for_discovery_review_count"],
                    summary["recheck_eligible_known_candidate_count"],
                    reviewed_by,
                    json.dumps(evidence),
                ),
            )
            batch_id = int(cur.fetchone()[0])

            for decision in decisions:
                cur.execute(
                    """
                    insert into aggregator_discovery_suppression_items (
                        batch_id,
                        aggregator_source_name,
                        company_name,
                        normalized_company_key,
                        silver_job_count,
                        first_seen_at,
                        last_seen_at,
                        decision,
                        handoff_action,
                        reason,
                        known_candidate_id,
                        known_candidate_status,
                        known_candidate_source_name,
                        recheck_eligible,
                        recheck_reason,
                        evidence
                    ) values (
                        %s, %s, %s, %s, %s,
                        %s::timestamptz, %s::timestamptz,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
                    )
                    """,
                    (
                        batch_id,
                        decision.aggregator_source_name,
                        decision.company,
                        decision.normalized_company_key,
                        decision.silver_job_count,
                        decision.first_seen_at,
                        decision.last_seen_at,
                        decision.decision,
                        decision.handoff_action,
                        decision.reason,
                        decision.known_candidate_id,
                        decision.known_candidate_status,
                        decision.known_candidate_source_name,
                        decision.recheck_eligible,
                        decision.recheck_reason,
                        json.dumps(asdict(decision)),
                    ),
                )

        self.conn.commit()
        return batch_id


def decision_summary(decisions: list[AggregatorSuppressionDecision]) -> dict[str, int]:
    suppressed_count = sum(1 for decision in decisions if decision.suppressed)
    recheck_count = sum(1 for decision in decisions if decision.recheck_eligible)
    kept_count = len(decisions) - suppressed_count

    return {
        "company_count": len(decisions),
        "suppressed_count": suppressed_count,
        "kept_for_discovery_review_count": kept_count,
        "recheck_eligible_known_candidate_count": recheck_count,
    }


def summarize_decisions(decisions: list[AggregatorSuppressionDecision]) -> list[str]:
    summary = decision_summary(decisions)

    lines = [
        "Aggregator Discovery Suppression Preview",
        f"company_count: {summary['company_count']}",
        f"suppressed_count: {summary['suppressed_count']}",
        f"kept_for_discovery_review_count: {summary['kept_for_discovery_review_count']}",
        f"recheck_eligible_known_candidate_count: {summary['recheck_eligible_known_candidate_count']}",
    ]

    for decision in decisions:
        lines.extend(
            [
                "---",
                f"aggregator_source_name: {decision.aggregator_source_name}",
                f"company: {decision.company}",
                f"normalized_company_key: {decision.normalized_company_key}",
                f"silver_job_count: {decision.silver_job_count}",
                f"first_seen_at: {decision.first_seen_at}",
                f"last_seen_at: {decision.last_seen_at}",
                f"decision: {decision.decision}",
                f"handoff_action: {decision.handoff_action}",
                f"reason: {decision.reason}",
            ]
        )
        if decision.known_candidate_id is not None:
            lines.append(f"known_candidate_id: {decision.known_candidate_id}")
            lines.append(f"known_candidate_status: {decision.known_candidate_status}")
            lines.append(f"known_candidate_source_name: {decision.known_candidate_source_name}")
            lines.append(f"recheck_eligible: {decision.recheck_eligible}")
            if decision.recheck_reason:
                lines.append(f"recheck_reason: {decision.recheck_reason}")

    return lines


def run_agent(args: argparse.Namespace) -> int:
    sources = tuple(args.aggregator_source)
    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        repo = SuppressionRepository(conn)
        known_candidates = repo.load_known_candidates()
        signals = repo.load_aggregator_company_signals(sources)

        decisions = [
            suppress_aggregator_signal(signal, known_candidates)
            for signal in signals
        ]
        selected = decisions[: args.limit] if args.limit is not None else decisions

        if args.write_snapshot:
            batch_id = repo.write_snapshot(
                decisions=selected,
                aggregator_sources=sources,
                reviewed_by=args.reviewed_by,
            )
        else:
            batch_id = None

    for line in summarize_decisions(selected):
        print(line)

    if batch_id is not None:
        print("---")
        print(f"snapshot_written: true")
        print(f"aggregator_discovery_suppression_batch_id: {batch_id}")
    else:
        print("---")
        print("snapshot_written: false")
        print(
            "NEXT: rerun with --write-snapshot to persist this "
            "review-state snapshot after inspection."
        )

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Preview DB-backed suppression of known employer-origin candidates "
            "from aggregator discovery output. No HTTP calls, no export inputs. "
            "Snapshot persistence is optional review-state only."
        )
    )
    parser.add_argument(
        "--aggregator-source",
        action="append",
        default=list(DEFAULT_AGGREGATOR_SOURCES),
        help="Aggregator source_name to inspect from silver_jobs. Defaults to stepstone.",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--write-snapshot",
        action="store_true",
        help=(
            "Persist the suppression result into DB review-state tables. "
            "Does not write Bronze or activate sources."
        ),
    )
    parser.add_argument("--reviewed-by", default="agent")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
