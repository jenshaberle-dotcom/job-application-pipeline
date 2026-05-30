"""DB-backed aggregator discovery suppression preview.

This agent reads known employer-origin candidates from PostgreSQL and compares them
with current aggregator-origin Silver company signals. It does not write to the DB,
does not call external websites and does not use exports as process inputs.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.aggregator_discovery_policy import (
    AggregatorSuppressionDecision,
    KnownEmployerCandidate,
    suppress_aggregator_company,
)


DEFAULT_AGGREGATOR_SOURCES = ("stepstone",)


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

    def load_aggregator_companies(self, sources: tuple[str, ...]) -> list[str]:
        if not sources:
            return []

        with self.conn.cursor() as cur:
            cur.execute(
                """
                select distinct normalized_company_name
                from silver_jobs
                where source_name = any(%s)
                    and normalized_company_name is not null
                    and btrim(normalized_company_name) <> ''
                order by normalized_company_name
                """,
                (list(sources),),
            )
            rows = cur.fetchall()

        return [str(row[0]) for row in rows]


def summarize_decisions(decisions: list[AggregatorSuppressionDecision]) -> list[str]:
    suppressed_count = sum(1 for decision in decisions if decision.suppressed)
    recheck_count = sum(1 for decision in decisions if decision.recheck_eligible)
    kept_count = len(decisions) - suppressed_count

    lines = [
        "Aggregator Discovery Suppression Preview",
        f"company_count: {len(decisions)}",
        f"suppressed_count: {suppressed_count}",
        f"kept_for_discovery_review_count: {kept_count}",
        f"recheck_eligible_known_candidate_count: {recheck_count}",
    ]

    for decision in decisions:
        lines.extend(
            [
                "---",
                f"company: {decision.company}",
                f"normalized_company_key: {decision.normalized_company_key}",
                f"decision: {decision.decision}",
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
        companies = repo.load_aggregator_companies(sources)

    decisions = [
        suppress_aggregator_company(company, known_candidates)
        for company in companies
    ]

    selected = decisions[: args.limit] if args.limit is not None else decisions
    for line in summarize_decisions(selected):
        print(line)

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Preview DB-backed suppression of known employer-origin candidates "
            "from aggregator discovery output. No writes, no HTTP calls, no export inputs."
        )
    )
    parser.add_argument(
        "--aggregator-source",
        action="append",
        default=list(DEFAULT_AGGREGATOR_SOURCES),
        help="Aggregator source_name to inspect from silver_jobs. Defaults to stepstone.",
    )
    parser.add_argument("--limit", type=int)
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
