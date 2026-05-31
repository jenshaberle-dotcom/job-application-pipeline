"""S5A false-negative intelligence preview agent.

Reads DB-backed market evidence and employer-origin candidate state, then reports
where aggregator evidence contradicts unresolved employer-origin decisions.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.search_intelligence.false_negative_risk import (
    CandidateMarketEvidenceSummary,
    FalseNegativeRiskAssessment,
    assess_many,
)


class DatabaseConfig:
    def __init__(self, host: str, port: str, dbname: str, user: str, password: str) -> None:
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password

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
        return f"host={self.host} port={self.port} dbname={self.dbname} user={self.user} password={self.password}"


class FalseNegativeRepository:
    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def load_candidate_market_evidence(self) -> list[CandidateMarketEvidenceSummary]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select
                    candidate_id,
                    company_key,
                    company_name,
                    candidate_status,
                    candidate_risk_level,
                    sighting_count,
                    recent_sighting_count,
                    last_observed_at::text as last_observed_at,
                    coalesce(evidence_sources, array[]::text[]) as evidence_sources,
                    coalesce(evidence_titles, array[]::text[]) as evidence_titles
                from candidate_market_evidence_summary
                order by recent_sighting_count desc, sighting_count desc, company_name
                """
            )
            rows = cur.fetchall()

        return [summary_from_row(row) for row in rows]

    def write_snapshot(
        self,
        *,
        assessments: list[FalseNegativeRiskAssessment],
        reviewed_by: str,
    ) -> int:
        count = 0
        with self.conn.cursor() as cur:
            for assessment in assessments:
                if assessment.risk_level == "low" and assessment.sighting_count == 0:
                    continue
                cur.execute(
                    """
                    insert into false_negative_risk_snapshots (
                        candidate_id,
                        company_key,
                        risk_level,
                        sighting_count,
                        recent_sighting_count,
                        last_observed_at,
                        suggested_search_terms,
                        reason,
                        evidence,
                        reviewed_by
                    ) values (%s, %s, %s, %s, %s, %s::timestamptz, %s, %s, %s::jsonb, %s)
                    """,
                    (
                        assessment.candidate_id,
                        assessment.company_key,
                        assessment.risk_level,
                        assessment.sighting_count,
                        assessment.recent_sighting_count,
                        assessment.last_observed_at,
                        list(assessment.suggested_search_terms),
                        assessment.reason,
                        json.dumps(asdict(assessment), ensure_ascii=False),
                        reviewed_by,
                    ),
                )
                count += 1
        self.conn.commit()
        return count


def summary_from_row(row: dict[str, Any]) -> CandidateMarketEvidenceSummary:
    return CandidateMarketEvidenceSummary(
        candidate_id=int(row["candidate_id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        candidate_status=str(row["candidate_status"]),
        candidate_risk_level=str(row["candidate_risk_level"]),
        sighting_count=int(row["sighting_count"] or 0),
        recent_sighting_count=int(row["recent_sighting_count"] or 0),
        last_observed_at=row["last_observed_at"],
        evidence_sources=tuple(row["evidence_sources"] or ()),
        evidence_titles=tuple(row["evidence_titles"] or ()),
    )


def print_assessments(assessments: list[FalseNegativeRiskAssessment], *, limit: int) -> None:
    shown = assessments[:limit]
    print("False Negative Intelligence Preview")
    print(f"candidate_count: {len(assessments)}")
    print(f"shown_count: {len(shown)}")
    for assessment in shown:
        print("---")
        print(f"company: {assessment.company_name}")
        print(f"company_key: {assessment.company_key}")
        print(f"risk_level: {assessment.risk_level}")
        print(f"sighting_count: {assessment.sighting_count}")
        print(f"recent_sighting_count: {assessment.recent_sighting_count}")
        print(f"last_observed_at: {assessment.last_observed_at}")
        print(f"sources: {', '.join(assessment.evidence_sources) or '-'}")
        print(f"suggested_search_terms: {', '.join(assessment.suggested_search_terms) or '-'}")
        print(f"reason: {assessment.reason}")
        if assessment.evidence_titles:
            print("titles:")
            for title in assessment.evidence_titles[:5]:
                print(f"- {title}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preview DB-backed false-negative risk from market evidence.")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--write-snapshot", action="store_true")
    parser.add_argument("--reviewed-by", default="agent")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        repo = FalseNegativeRepository(conn)
        assessments = assess_many(repo.load_candidate_market_evidence())
        print_assessments(assessments, limit=args.limit)
        if args.write_snapshot:
            written = repo.write_snapshot(assessments=assessments, reviewed_by=args.reviewed_by)
            print("---")
            print("snapshot_written: true")
            print(f"false_negative_risk_snapshot_count: {written}")
        else:
            print("---")
            print("snapshot_written: false")
            print("NEXT: rerun with --write-snapshot after inspection to persist this false-negative review state.")


if __name__ == "__main__":
    main()
