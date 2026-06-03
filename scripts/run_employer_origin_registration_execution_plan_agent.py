from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config

PLAN_DIR = Path("docs/source_analysis")


@dataclass(frozen=True)
class SourceCandidate:
    id: int
    company_key: str
    company_name: str
    source_name_candidate: str
    source_family_candidate: str
    source_type_candidate: str
    status: str


@dataclass(frozen=True)
class GateReview:
    gate_name: str
    gate_status: str
    decision: str
    stop_reason: str | None


@dataclass(frozen=True)
class ExecutionPlan:
    candidate: SourceCandidate
    allowed: bool
    reason: str
    steps: tuple[str, ...]
    validation: tuple[str, ...]
    rollback: tuple[str, ...]
    forbidden: tuple[str, ...]
    evidence: dict[str, Any]


def snake_case(value: str) -> str:
    import re

    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", normalized).strip("_")


def final_approval_passed(gates: dict[str, GateReview]) -> bool:
    gate = gates.get("final_approval_gate")
    return bool(gate and gate.gate_status == "passed" and gate.decision == "approve_connector_registration")


def build_execution_plan(candidate: SourceCandidate, gates: dict[str, GateReview]) -> ExecutionPlan:
    module_name = snake_case(candidate.source_family_candidate)
    if candidate.status == "active_controlled":
        allowed = False
        reason = "candidate is already active_controlled"
    else:
        allowed = final_approval_passed(gates)
        reason = (
            "final approval gate passed"
            if allowed
            else "final approval gate is not passed/approve_connector_registration"
        )

    steps = (
        f"Register `{candidate.source_name_candidate}` in the code-backed connector registry, not directly in CLI control flow.",
        f"Import `src.connectors.{module_name}` and its connector class from the employer-origin registry extension.",
        "Run connector-specific tests and full test suite.",
        "Run a bounded manual ingestion preview if supported.",
        "Prepare a separate controlled activation migration/search-profile change.",
    )

    validation = (
        "python -m compileall src scripts tests",
        "pytest -q",
        f"python -m scripts.run_employer_origin_connector_validation_agent --company-key {candidate.company_key}",
        f"python -m scripts.run_employer_origin_agent_chain --company-key {candidate.company_key} --reviewed-by jens --plan-only",
    )

    rollback = (
        "Remove connector mapping from the code-backed connector registry.",
        "Revert source-profile activation migration if created in a later activation PR.",
        "Keep raw_jobs unchanged unless a later controlled activation wrote new rows.",
    )

    forbidden = (
        "Do not enable recurring ingestion in this execution plan.",
        "Do not write Bronze rows in this execution plan.",
        "Do not create or enable scheduler changes in this execution plan.",
        "Do not use CSV/Excel/export artifacts as inputs.",
    )

    evidence = {
        "agent": "s4c_registration_execution_plan_agent",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "allowed": allowed,
        "reason": reason,
        "candidate": {
            "candidate_id": candidate.id,
            "company_key": candidate.company_key,
            "source_name_candidate": candidate.source_name_candidate,
            "source_type_candidate": candidate.source_type_candidate,
            "status": candidate.status,
        },
        "boundary": {
            "connector_registration_plan_only": True,
            "registration_target": "src.connectors.registry / src.connectors.employer_origin_registry",
            "source_activation_allowed": False,
            "bronze_persistence_allowed": False,
            "recurring_ingestion_allowed": False,
            "csv_or_export_inputs_used": False,
        },
    }

    return ExecutionPlan(
        candidate=candidate,
        allowed=allowed,
        reason=reason,
        steps=steps,
        validation=validation,
        rollback=rollback,
        forbidden=forbidden,
        evidence=evidence,
    )


def render_markdown(plan: ExecutionPlan) -> str:
    return "\n".join(
        [
            f"# Registration Execution Plan — {plan.candidate.company_key}",
            "",
            "## Status",
            "",
            f"- allowed: `{str(plan.allowed).lower()}`",
            f"- reason: {plan.reason}",
            "",
            "## Registration Steps",
            "",
            *[f"- {step}" for step in plan.steps],
            "",
            "## Validation",
            "",
            *[f"- `{step}`" for step in plan.validation],
            "",
            "## Rollback",
            "",
            *[f"- {step}" for step in plan.rollback],
            "",
            "## Forbidden Actions",
            "",
            *[f"- {step}" for step in plan.forbidden],
            "",
            "## Boundary",
            "",
            "This is an execution plan only. It does not modify connector registration, activation, Bronze persistence or scheduler state.",
            "",
        ]
    )


def plan_path(candidate: SourceCandidate) -> Path:
    return PLAN_DIR / f"{snake_case(candidate.company_key)}_registration_execution_plan.md"


class ExecutionPlanRepository:
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
            company_name=str(row["company_name"]),
            source_name_candidate=str(row["source_name_candidate"]),
            source_family_candidate=str(row["source_family_candidate"]),
            source_type_candidate=str(row["source_type_candidate"]),
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


def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(**get_database_config()) as conn:
        repo = ExecutionPlanRepository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=args.company_key)
        gates = repo.load_gates(candidate.id)

    plan = build_execution_plan(candidate, gates)

    print(f"candidate_id: {candidate.id}")
    print(f"candidate: {candidate.company_key} | {candidate.source_name_candidate}")
    print(f"registration_execution_plan_allowed: {str(plan.allowed).lower()}")
    print(f"reason: {plan.reason}")

    if args.write:
        path = plan_path(candidate)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(plan), encoding="utf-8")
        print(f"wrote_plan: {path}")

    if args.print_json:
        print(json.dumps(plan.evidence, indent=2, ensure_ascii=False, default=str))

    return 0 if plan.allowed else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare a connector registration execution plan after final approval.")
    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
