from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row


FINAL_APPROVAL_GATE = "final_approval_gate"
APPROVAL_TOKEN = "approve_connector_registration"


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
    source_name_candidate: str
    status: str


@dataclass(frozen=True)
class GateReview:
    gate_name: str
    gate_status: str
    decision: str
    stop_reason: str | None


@dataclass(frozen=True)
class ApprovalOutcome:
    gate_status: str
    decision: str
    stop_reason: str | None
    evidence: dict[str, Any]


def validation_ready(gates: dict[str, GateReview]) -> bool:
    gate = gates.get("connector_validation_gate")
    return bool(gate and gate.gate_status == "passed" and gate.decision == "ready_for_final_approval")


def evaluate_final_approval(
    *,
    candidate: SourceCandidate,
    gates: dict[str, GateReview],
    approval_token: str | None,
    approved_by: str,
) -> ApprovalOutcome:
    if candidate.status == "active_controlled":
        evidence = {
            "agent": "s3e_final_approval_gate_agent",
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "candidate": {
                "candidate_id": candidate.id,
                "company_key": candidate.company_key,
                "source_name_candidate": candidate.source_name_candidate,
                "status": candidate.status,
            },
            "approval_token_required": APPROVAL_TOKEN,
            "approval_token_provided": approval_token == APPROVAL_TOKEN,
            "approved_by": approved_by,
            "boundary": {
                "connector_registration_allowed_after_this_gate": False,
                "source_activation_allowed": False,
                "bronze_persistence_allowed": False,
                "recurring_ingestion_allowed": False,
                "csv_or_export_inputs_used": False,
            },
        }
        return ApprovalOutcome(
            gate_status="not_applicable",
            decision="monitor_existing_source",
            stop_reason="candidate is already active_controlled",
            evidence=evidence,
        )

    evidence = {
        "agent": "s3e_final_approval_gate_agent",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "candidate": {
            "candidate_id": candidate.id,
            "company_key": candidate.company_key,
            "source_name_candidate": candidate.source_name_candidate,
            "status": candidate.status,
        },
        "approval_token_required": APPROVAL_TOKEN,
        "approval_token_provided": approval_token == APPROVAL_TOKEN,
        "approved_by": approved_by,
        "boundary": {
            "connector_registration_allowed_after_this_gate": True,
            "source_activation_allowed": False,
            "bronze_persistence_allowed": False,
            "recurring_ingestion_allowed": False,
            "csv_or_export_inputs_used": False,
        },
    }

    if not validation_ready(gates):
        return ApprovalOutcome(
            gate_status="manual_review_required",
            decision="approval_blocked",
            stop_reason="connector_validation_gate is not passed/ready_for_final_approval",
            evidence=evidence,
        )

    if approval_token != APPROVAL_TOKEN:
        return ApprovalOutcome(
            gate_status="manual_review_required",
            decision="approval_token_required",
            stop_reason="explicit approval token is required",
            evidence=evidence,
        )

    return ApprovalOutcome(
        gate_status="passed",
        decision="approve_connector_registration",
        stop_reason=None,
        evidence=evidence,
    )


def approval_lines(candidate: SourceCandidate, outcome: ApprovalOutcome) -> list[str]:
    lines = [
        f"candidate_id: {candidate.id}",
        f"candidate: {candidate.company_key} | {candidate.source_name_candidate}",
        f"{FINAL_APPROVAL_GATE}: {outcome.gate_status} / {outcome.decision}",
    ]
    if outcome.stop_reason:
        lines.append(f"STOP: {outcome.stop_reason}")
    else:
        lines.append("NEXT: registration execution plan may be prepared. Controlled activation remains separate.")
    return lines


class ApprovalRepository:
    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def load_candidate(self, *, candidate_id: int | None, company_key: str | None) -> SourceCandidate:
        if candidate_id is None and not company_key:
            raise ValueError("Either candidate_id or company_key is required.")

        with self.conn.cursor(row_factory=dict_row) as cur:
            if candidate_id is not None:
                cur.execute("select * from employer_origin_source_candidates where id = %s", (candidate_id,))
            else:
                cur.execute(
                    """
                    select *
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
            source_name_candidate=str(row["source_name_candidate"]),
            status=str(row["status"]),
        )

    def load_gates(self, candidate_id: int) -> dict[str, GateReview]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select gate_name, gate_status, decision, stop_reason
                from employer_origin_candidate_gate_reviews
                where candidate_id = %s
                """,
                (candidate_id,),
            )
            rows = cur.fetchall()

        return {
            str(row["gate_name"]): GateReview(
                gate_name=str(row["gate_name"]),
                gate_status=str(row["gate_status"]),
                decision=str(row["decision"]),
                stop_reason=row["stop_reason"],
            )
            for row in rows
        }

    def record_gate(self, *, candidate_id: int, outcome: ApprovalOutcome) -> None:
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
                values (%s, 16, %s, %s, %s, %s, %s, %s)
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
                    FINAL_APPROVAL_GATE,
                    outcome.gate_status,
                    outcome.decision,
                    outcome.stop_reason,
                    json.dumps(outcome.evidence),
                    outcome.evidence["approved_by"],
                ),
            )


def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        repo = ApprovalRepository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=args.company_key)
        gates = repo.load_gates(candidate.id)
        outcome = evaluate_final_approval(
            candidate=candidate,
            gates=gates,
            approval_token=args.approval_token,
            approved_by=args.approved_by,
        )

        if not args.dry_run:
            repo.record_gate(candidate_id=candidate.id, outcome=outcome)
            conn.commit()

    for line in approval_lines(candidate, outcome):
        print(line)

    if args.dry_run:
        print("DRY RUN: no DB gate state was changed.")

    if args.print_json:
        print(json.dumps(outcome.evidence, indent=2, ensure_ascii=False, default=str))

    return 0 if outcome.gate_status in {"passed", "not_applicable"} else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record explicit final approval for connector registration.")
    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")
    parser.add_argument("--approval-token")
    parser.add_argument("--approved-by", default="jens")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
