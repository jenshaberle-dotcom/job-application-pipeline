from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config

DETAIL_EVIDENCE_GATE = "detail_evidence_gate"
CONNECTOR_CANDIDATE_GATE = "connector_candidate_gate"
CONNECTOR_VALIDATION_GATE = "connector_validation_gate"
FINAL_APPROVAL_GATE = "final_approval_gate"
SOURCE_LIFECYCLE_GATE = "source_lifecycle_tracking"
APPROVAL_TOKEN = "approve_connector_registration"

REQUIRED_CONNECTOR_ARTIFACT_GATES = (
    "company_candidate",
    "source_discovery",
    "risk_gate",
    "technical_reachability_gate",
    "scope_gate",
    "defensive_preview_gate",
    "relevance_gate",
    "detail_evidence_gate",
    "incremental_uniqueness_gate",
    "connector_candidate_gate",
)


@dataclass(frozen=True)
class SourceCandidate:
    id: int
    company_key: str
    company_name: str
    source_name_candidate: str
    source_family_candidate: str
    status: str


@dataclass(frozen=True)
class GateReview:
    gate_name: str
    gate_status: str
    decision: str
    stop_reason: str | None
    evidence: dict[str, Any] | None = None


@dataclass(frozen=True)
class ChainDecision:
    action: str
    reason: str
    module: str | None = None
    args: tuple[str, ...] = ()


def snake_case(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", normalized).strip("_")


def connector_module_name(source_family_candidate: str) -> str:
    return snake_case(source_family_candidate)


def connector_artifact_paths(source_family_candidate: str) -> tuple[Path, Path, Path]:
    module_name = connector_module_name(source_family_candidate)
    return (
        Path("src/connectors") / f"{module_name}.py",
        Path("tests") / f"test_{module_name}_connector.py",
        Path("docs/planning/active/source-candidates") / f"{module_name}_connector_candidate.md",
    )


def connector_artifacts_exist(source_family_candidate: str) -> bool:
    return all(path.exists() for path in connector_artifact_paths(source_family_candidate))


def load_candidate(conn: psycopg.Connection[Any], company_key: str) -> SourceCandidate:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select
                id,
                company_key,
                company_name,
                source_name_candidate,
                source_family_candidate,
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
        source_family_candidate=str(row["source_family_candidate"]),
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
                stop_reason,
                evidence
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
            evidence=dict(row["evidence"] or {}),
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


def connector_validation_ready(gates: dict[str, GateReview]) -> bool:
    return gate_passed(gates.get(CONNECTOR_VALIDATION_GATE), decision="ready_for_final_approval")


def final_approval_ready(gates: dict[str, GateReview]) -> bool:
    return gate_passed(gates.get(FINAL_APPROVAL_GATE), decision=APPROVAL_TOKEN)


def connector_candidate_spec(gates: dict[str, GateReview]) -> dict[str, Any]:
    gate = gates.get(CONNECTOR_CANDIDATE_GATE)
    if gate is None:
        return {}
    evidence = gate.evidence or {}
    spec = evidence.get("connector_candidate_spec") or {}
    return spec if isinstance(spec, dict) else {}


def connector_candidate_has_detail_urls(gates: dict[str, GateReview]) -> bool:
    spec = connector_candidate_spec(gates)
    detail = spec.get("detail_evidence") or {}
    urls = detail.get("detail_urls") or []
    return any(str(url).startswith(("http://", "https://")) for url in urls)


def connector_artifact_generation_ready(gates: dict[str, GateReview]) -> bool:
    for gate_name in REQUIRED_CONNECTOR_ARTIFACT_GATES:
        gate = gates.get(gate_name)
        if gate is None or gate.gate_status != "passed":
            return False

    if not connector_candidate_ready(gates):
        return False

    return connector_candidate_has_detail_urls(gates)


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


def connector_build_readiness_args(company_key: str) -> tuple[str, ...]:
    return ("--company-key", company_key)


def connector_artifact_generator_args(company_key: str, write_connector: bool) -> tuple[str, ...]:
    args = ["--company-key", company_key]
    if not write_connector:
        args.append("--dry-run")
    return tuple(args)


def connector_validation_args(company_key: str, reviewed_by: str) -> tuple[str, ...]:
    return ("--company-key", company_key, "--reviewed-by", reviewed_by)


def final_approval_args(company_key: str, reviewed_by: str, approval_token: str) -> tuple[str, ...]:
    return (
        "--company-key",
        company_key,
        "--approved-by",
        reviewed_by,
        "--approval-token",
        approval_token,
    )


def registration_execution_plan_args(company_key: str, write_registration_plan: bool) -> tuple[str, ...]:
    args = ["--company-key", company_key]
    if write_registration_plan:
        args.append("--write")
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
    artifacts_exist: bool = False,
    approval_token: str | None = None,
    write_registration_plan: bool = False,
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

    if not connector_artifact_generation_ready(gates):
        return ChainDecision(
            action="run_connector_build_readiness_agent",
            reason="connector_candidate_gate is passed, but full S4A artifact-generation readiness is not satisfied",
            module="scripts.run_employer_origin_connector_build_readiness_agent",
            args=connector_build_readiness_args(company_key),
        )

    if not artifacts_exist:
        return ChainDecision(
            action="run_connector_artifact_generator",
            reason="all required S4A gates are passed, but connector artifact files do not exist yet",
            module="scripts.run_employer_origin_connector_artifact_generator",
            args=connector_artifact_generator_args(company_key, write_connector),
        )

    if not connector_validation_ready(gates):
        return ChainDecision(
            action="run_connector_validation_agent",
            reason="connector artifact files exist, but connector_validation_gate is not passed/ready_for_final_approval",
            module="scripts.run_employer_origin_connector_validation_agent",
            args=connector_validation_args(company_key, reviewed_by),
        )

    if not final_approval_ready(gates):
        if approval_token == APPROVAL_TOKEN:
            return ChainDecision(
                action="run_final_approval_gate_agent",
                reason="connector_validation_gate is passed and explicit approval token was provided",
                module="scripts.run_employer_origin_final_approval_gate_agent",
                args=final_approval_args(company_key, reviewed_by, approval_token),
            )

        return ChainDecision(
            action="stop_explicit_approval_required",
            reason=(
                "connector_validation_gate is passed/ready_for_final_approval; explicit "
                f"approval token {APPROVAL_TOKEN!r} is required before registration planning"
            ),
        )

    return ChainDecision(
        action="run_registration_execution_plan_agent",
        reason="final_approval_gate is passed; prepare non-activating connector registration execution plan",
        module="scripts.run_employer_origin_registration_execution_plan_agent",
        args=registration_execution_plan_args(company_key, write_registration_plan),
    )


def print_gate_summary(candidate: SourceCandidate, gates: dict[str, GateReview]) -> None:
    print(f"candidate_id: {candidate.id}")
    print(f"candidate: {candidate.company_key} | {candidate.source_name_candidate}")
    print("gate_state:")
    for gate_name in sorted(gates):
        gate = gates[gate_name]
        suffix = f" | stop_reason={gate.stop_reason}" if gate.stop_reason else ""
        print(f"- {gate.gate_name}: {gate.gate_status} / {gate.decision}{suffix}")


def print_artifact_summary(candidate: SourceCandidate) -> None:
    paths = connector_artifact_paths(candidate.source_family_candidate)
    print("connector_artifacts:")
    for path in paths:
        print(f"- {path}: {'present' if path.exists() else 'missing'}")


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
            "NEXT: rerun this chain command to continue from refreshed DB gate/file state.",
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
    with psycopg.connect(**get_database_config()) as conn:
        candidate = load_candidate(conn, args.company_key)
        gates = load_gate_reviews(conn, candidate.id)

    print_gate_summary(candidate, gates)
    print_artifact_summary(candidate)

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
        artifacts_exist=connector_artifacts_exist(candidate.source_family_candidate),
        approval_token=args.approval_token,
        write_registration_plan=args.write_registration_plan,
    )

    print(f"next_action: {decision.action}")
    print(f"reason: {decision.reason}")

    if args.plan_only or decision.module is None:
        if decision.module:
            print("planned_command:", " ".join(child_command(decision.module, decision.args)))
        return 0 if not decision.action.startswith("stop_") else 2

    exit_code = run_child(decision)
    for line in child_exit_interpretation_lines(exit_code):
        print(line)
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "DB-backed employer-origin agent chain driver. It inspects current gate/file state, "
            "runs only the next bounded agent step, and then asks to rerun against refreshed state."
        )
    )
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--attempt-repair", action="store_true")
    parser.add_argument("--write-connector", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--write-registration-plan", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
