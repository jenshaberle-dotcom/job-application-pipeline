from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row


DETAIL_EVIDENCE_GATE = "detail_evidence_gate"
CONNECTOR_CANDIDATE_GATE = "connector_candidate_gate"
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


@dataclass(frozen=True)
class GateReview:
    gate_name: str
    gate_status: str
    decision: str
    stop_reason: str | None


@dataclass(frozen=True)
class ChainDecision:
    action: str
    reason: str
    module: str | None = None
    args: tuple[str, ...] = ()


def load_candidate(conn: psycopg.Connection[Any], company_key: str) -> SourceCandidate:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select
                id,
                company_key,
                company_name,
                source_name_candidate,
                status
            from employer_origin_source_candidates
            where company_key = %s
            order by id desc
            limit 1
            """,
            (company_key,),
        )
        row = cur.fetchone()

    if row is None:
        raise ValueError(f"No employer-origin source candidate found for company_key={company_key!r}.")

    return SourceCandidate(
        id=int(row["id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        source_name_candidate=str(row["source_name_candidate"]),
        status=str(row["status"]),
    )


def load_gate_reviews(conn: psycopg.Connection[Any], candidate_id: int) -> dict[str, GateReview]:
    with conn.cursor(row_factory=dict_row) as cur:
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

    return {
        str(row["gate_name"]): GateReview(
            gate_name=str(row["gate_name"]),
            gate_status=str(row["gate_status"]),
            decision=str(row["decision"]),
            stop_reason=row["stop_reason"],
        )
        for row in rows
    }


def gate_passed(gate: GateReview | None, *, decision: str | None = None) -> bool:
    if gate is None:
        return False
    if gate.gate_status != "passed":
        return False
    if decision is not None and gate.decision != decision:
        return False
    return True


def needs_detail_evidence_repair(gates: dict[str, GateReview]) -> bool:
    return not gate_passed(gates.get(DETAIL_EVIDENCE_GATE))


def connector_candidate_ready(gates: dict[str, GateReview]) -> bool:
    return gate_passed(gates.get(CONNECTOR_CANDIDATE_GATE), decision="build_connector_candidate")


def child_command(module: str, args: tuple[str, ...]) -> list[str]:
    return [sys.executable, "-m", module, *args]


def repair_args(company_key: str, target_location: str, reviewed_by: str) -> tuple[str, ...]:
    return (
        "--company-key",
        company_key,
        "--target-location",
        target_location,
        "--reviewed-by",
        reviewed_by,
    )


def connector_candidate_args(company_key: str, reviewed_by: str) -> tuple[str, ...]:
    return (
        "--company-key",
        company_key,
        "--reviewed-by",
        reviewed_by,
    )


def connector_implementation_args(company_key: str, write_connector: bool) -> tuple[str, ...]:
    args = ["--company-key", company_key]
    if not write_connector:
        args.append("--dry-run")
    return tuple(args)


def active_controlled_source_completed(
    candidate: SourceCandidate,
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

def next_decision(
    gates: dict[str, GateReview],
    *,
    company_key: str,
    target_location: str,
    reviewed_by: str,
    attempt_repair: bool,
    write_connector: bool,
) -> ChainDecision:
    if needs_detail_evidence_repair(gates):
        detail_gate = gates.get(DETAIL_EVIDENCE_GATE)
        reason = "detail_evidence_gate is not passed"
        if detail_gate and detail_gate.stop_reason:
            reason = f"{reason}: {detail_gate.stop_reason}"

        if attempt_repair:
            return ChainDecision(
                action="run_detail_evidence_repair",
                reason=reason,
                module="scripts.run_employer_origin_detail_evidence_repair_agent",
                args=repair_args(company_key, target_location, reviewed_by),
            )

        return ChainDecision(
            action="stop_manual_review_required",
            reason=f"{reason}; rerun with --attempt-repair for bounded same-domain repair.",
        )

    if not connector_candidate_ready(gates):
        return ChainDecision(
            action="run_connector_candidate_gate",
            reason="detail_evidence_gate is passed but connector_candidate_gate is not ready",
            module="scripts.run_employer_origin_connector_candidate_agent",
            args=connector_candidate_args(company_key, reviewed_by),
        )

    return ChainDecision(
        action="run_connector_implementation_agent",
        reason="connector_candidate_gate is passed/build_connector_candidate",
        module="scripts.run_employer_origin_connector_implementation_agent",
        args=connector_implementation_args(company_key, write_connector),
    )


def print_gate_summary(candidate: SourceCandidate, gates: dict[str, GateReview]) -> None:
    print(f"candidate_id: {candidate.id}")
    print(f"candidate: {candidate.company_key} | {candidate.source_name_candidate}")
    print("gate_state:")
    for gate_name in sorted(gates):
        gate = gates[gate_name]
        suffix = f" | stop_reason={gate.stop_reason}" if gate.stop_reason else ""
        print(f"- {gate.gate_name}: {gate.gate_status} / {gate.decision}{suffix}")


def run_child(decision: ChainDecision) -> int:
    if not decision.module:
        return 0

    command = child_command(decision.module, decision.args)
    print("running:", " ".join(command))
    completed = subprocess.run(command, check=False)
    return int(completed.returncode)


def child_exit_interpretation_lines(exit_code: int) -> list[str]:
    if exit_code == 0:
        return [
            "child_step_completed: true",
            "NEXT: rerun this chain command to continue from refreshed DB gate state.",
        ]

    if exit_code == 2:
        return [
            "child_step_completed: false",
            "child_gate_outcome: manual_review_required",
            "NEXT: inspect DB gate state or rerun with a different bounded option after manual review.",
        ]

    return [
        f"child_exit_code: {exit_code}",
    ]

def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        candidate = load_candidate(conn, args.company_key)
        gates = load_gate_reviews(conn, candidate.id)

    print_gate_summary(candidate, gates)

    if active_controlled_source_completed(candidate, gates):
        print("next_action: monitor_source_lifecycle")
        print("reason: source is active_controlled and all tracked gates are passed")
        print("No connector candidate files were written.")
        return 0

    decision = next_decision(
        gates,
        company_key=args.company_key,
        target_location=args.target_location,
        reviewed_by=args.reviewed_by,
        attempt_repair=args.attempt_repair,
        write_connector=args.write_connector,
    )

    print(f"next_action: {decision.action}")
    print(f"reason: {decision.reason}")

    if args.plan_only or decision.module is None:
        if decision.module:
            print("planned_command:", " ".join(child_command(decision.module, decision.args)))
        return 0 if decision.action != "stop_manual_review_required" else 2

    exit_code = run_child(decision)
    for line in child_exit_interpretation_lines(exit_code):
        print(line)
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "DB-backed employer-origin agent chain driver. It inspects current gate state, "
            "runs only the next bounded agent step, and then asks to rerun against refreshed DB state."
        )
    )
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--attempt-repair", action="store_true")
    parser.add_argument("--write-connector", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
