from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_agent_chain import (
    CONNECTOR_CANDIDATE_GATE,
    GateReview,
    next_decision,
)


SOURCE_LIFECYCLE_GATE = "source_lifecycle_tracking"


@dataclass(frozen=True)
class CandidateSummary:
    candidate_id: int
    company_key: str
    company_name: str
    source_name_candidate: str
    status: str
    risk_level: str
    latest_gate_order: int | None
    latest_gate_name: str | None
    blocked_gate_count: int
    manual_review_gate_count: int
    passed_gate_count: int
    total_gate_count: int


@dataclass(frozen=True)
class QueueItem:
    candidate: CandidateSummary
    next_action: str
    reason: str
    priority: int
    command: str | None


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


def gate_from_row(row: dict[str, Any]) -> GateReview:
    return GateReview(
        gate_name=str(row["gate_name"]),
        gate_status=str(row["gate_status"]),
        decision=str(row["decision"]),
        stop_reason=row["stop_reason"],
    )


def build_chain_command(
    *,
    company_key: str,
    target_location: str,
    reviewed_by: str,
    attempt_repair: bool,
    write_connector: bool = False,
) -> str:
    parts = [
        "python",
        "-m",
        "scripts.run_employer_origin_agent_chain",
        "--company-key",
        company_key,
        "--target-location",
        target_location,
        "--reviewed-by",
        reviewed_by,
    ]
    if attempt_repair:
        parts.append("--attempt-repair")
    if write_connector:
        parts.append("--write-connector")
    return " ".join(parts)


def build_lifecycle_command(*, company_key: str, reviewed_by: str) -> str:
    return (
        "python -m scripts.run_employer_origin_source_lifecycle_tracking_agent "
        f"--company-key {company_key} --reviewed-by {reviewed_by}"
    )


def completed_active_controlled_source(
    candidate: CandidateSummary,
    gates: dict[str, GateReview],
) -> bool:
    if candidate.status != "active_controlled":
        return False

    lifecycle_gate = gates.get(SOURCE_LIFECYCLE_GATE)
    if lifecycle_gate is None or lifecycle_gate.gate_status != "passed":
        return False

    return all(
        gate.gate_status not in {"blocked", "manual_review_required"}
        for gate in gates.values()
    )

def detail_evidence_repair_exhausted(gates: dict[str, GateReview]) -> bool:
    detail_gate = gates.get("detail_evidence_gate")
    if detail_gate is None:
        return False

    stop_reason = (detail_gate.stop_reason or "").lower()
    return (
        detail_gate.gate_status == "manual_review_required"
        and "bounded repair found no concrete detail pages" in stop_reason
    )

def lifecycle_gate_missing_or_not_passed(gates: dict[str, GateReview]) -> bool:
    lifecycle = gates.get(SOURCE_LIFECYCLE_GATE)
    return lifecycle is None or lifecycle.gate_status != "passed"


def classify_queue_item(
    candidate: CandidateSummary,
    gates: dict[str, GateReview],
    *,
    target_location: str,
    reviewed_by: str,
    allow_repair: bool,
) -> QueueItem:
    if completed_active_controlled_source(candidate, gates):
        return QueueItem(
            candidate=candidate,
            next_action="monitor_source_lifecycle",
            reason="source is active_controlled and all tracked gates are passed",
            priority=100,
            command=None,
        )

    if candidate.status == "active_controlled" and lifecycle_gate_missing_or_not_passed(gates):
        return QueueItem(
            candidate=candidate,
            next_action="run_source_lifecycle_tracking",
            reason="active controlled source is missing a passed lifecycle gate",
            priority=10,
            command=build_lifecycle_command(
                company_key=candidate.company_key,
                reviewed_by=reviewed_by,
            ),
        )

    if detail_evidence_repair_exhausted(gates):
        return QueueItem(
            candidate=candidate,
            next_action="manual_review_stop",
            reason=(
                "detail evidence repair was already attempted and found no concrete "
                "detail pages with profile and target/remote signals"
            ),
            priority=95,
            command=None,
        )

    chain_decision = next_decision(
        gates,
        company_key=candidate.company_key,
        target_location=target_location,
        reviewed_by=reviewed_by,
        attempt_repair=allow_repair,
        write_connector=False,
    )

    command = None
    if chain_decision.action != "stop_manual_review_required":
        command = build_chain_command(
            company_key=candidate.company_key,
            target_location=target_location,
            reviewed_by=reviewed_by,
            attempt_repair=allow_repair,
            write_connector=False,
        )

    priority_by_action = {
        "run_connector_artifact_generator": 20,
        "run_connector_build_readiness_agent": 25,
        "run_connector_candidate_gate": 30,
        "run_detail_evidence_repair": 40,
        "stop_manual_review_required": 90,
    }

    return QueueItem(
        candidate=candidate,
        next_action=chain_decision.action,
        reason=chain_decision.reason,
        priority=priority_by_action.get(chain_decision.action, 80),
        command=command,
    )


def sort_queue_items(items: list[QueueItem]) -> list[QueueItem]:
    return sorted(
        items,
        key=lambda item: (
            item.priority,
            item.candidate.company_key,
            item.candidate.candidate_id,
        ),
    )


def render_queue(items: list[QueueItem], *, limit: int | None = None) -> list[str]:
    selected = items[:limit] if limit is not None else items
    lines = [
        "Employer-Origin Candidate Queue",
        f"candidate_count: {len(items)}",
    ]

    for item in selected:
        candidate = item.candidate
        lines.extend(
            [
                "---",
                f"candidate_id: {candidate.candidate_id}",
                f"company_key: {candidate.company_key}",
                f"source_name_candidate: {candidate.source_name_candidate}",
                f"status: {candidate.status}",
                f"risk_level: {candidate.risk_level}",
                f"passed/manual/blocked/total gates: "
                f"{candidate.passed_gate_count}/"
                f"{candidate.manual_review_gate_count}/"
                f"{candidate.blocked_gate_count}/"
                f"{candidate.total_gate_count}",
                f"next_action: {item.next_action}",
                f"reason: {item.reason}",
            ]
        )
        if item.command:
            lines.append(f"command: {item.command}")

    return lines


class QueueRepository:
    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def load_candidates(self) -> list[CandidateSummary]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select
                    c.id as candidate_id,
                    c.company_key,
                    c.company_name,
                    c.source_name_candidate,
                    c.status,
                    c.risk_level,
                    max(g.gate_order)::int as latest_gate_order,
                    (
                        array_agg(g.gate_name order by g.gate_order desc)
                        filter (where g.gate_name is not null)
                    )[1] as latest_gate_name,
                    count(*) filter (where g.gate_status = 'blocked')::int as blocked_gate_count,
                    count(*) filter (where g.gate_status = 'manual_review_required')::int as manual_review_gate_count,
                    count(*) filter (where g.gate_status = 'passed')::int as passed_gate_count,
                    count(g.id)::int as total_gate_count
                from employer_origin_source_candidates c
                left join employer_origin_candidate_gate_reviews g
                    on g.candidate_id = c.id
                group by
                    c.id,
                    c.company_key,
                    c.company_name,
                    c.source_name_candidate,
                    c.status,
                    c.risk_level
                order by c.company_key
                """
            )
            rows = cur.fetchall()

        return [
            CandidateSummary(
                candidate_id=int(row["candidate_id"]),
                company_key=str(row["company_key"]),
                company_name=str(row["company_name"]),
                source_name_candidate=str(row["source_name_candidate"]),
                status=str(row["status"]),
                risk_level=str(row["risk_level"]),
                latest_gate_order=row["latest_gate_order"],
                latest_gate_name=row["latest_gate_name"],
                blocked_gate_count=int(row["blocked_gate_count"]),
                manual_review_gate_count=int(row["manual_review_gate_count"]),
                passed_gate_count=int(row["passed_gate_count"]),
                total_gate_count=int(row["total_gate_count"]),
            )
            for row in rows
        ]

    def load_gate_reviews(self, candidate_id: int) -> dict[str, GateReview]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select
                    gate_name,
                    gate_status,
                    decision,
                    stop_reason
                from employer_origin_candidate_gate_reviews
                where candidate_id = %s
                """,
                (candidate_id,),
            )
            rows = cur.fetchall()

        return {str(row["gate_name"]): gate_from_row(row) for row in rows}


def build_queue(
    candidates: list[CandidateSummary],
    gates_by_candidate_id: dict[int, dict[str, GateReview]],
    *,
    target_location: str,
    reviewed_by: str,
    allow_repair: bool,
) -> list[QueueItem]:
    items = [
        classify_queue_item(
            candidate,
            gates_by_candidate_id.get(candidate.candidate_id, {}),
            target_location=target_location,
            reviewed_by=reviewed_by,
            allow_repair=allow_repair,
        )
        for candidate in candidates
    ]

    return sort_queue_items(items)


def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        repo = QueueRepository(conn)
        candidates = repo.load_candidates()
        gates_by_candidate_id = {
            candidate.candidate_id: repo.load_gate_reviews(candidate.candidate_id)
            for candidate in candidates
        }

    queue = build_queue(
        candidates,
        gates_by_candidate_id,
        target_location=args.target_location,
        reviewed_by=args.reviewed_by,
        allow_repair=args.allow_repair,
    )

    for line in render_queue(queue, limit=args.limit):
        print(line)

    if args.print_next_command:
        next_command = next((item.command for item in queue if item.command), None)
        if next_command:
            print("---")
            print("next_command:")
            print(next_command)
        else:
            print("---")
            print("next_command:")
            print("-")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "DB-backed queue view for employer-origin candidates. "
            "It proposes the next bounded agent command without executing it."
        )
    )
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--allow-repair", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--print-next-command", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
