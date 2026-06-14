"""RETIRED: historical artifact only.

This script was removed from active project paths by CONSISTENCY-001B.
It must not be executed as active pipeline steering and must not be used as
chat/handover/NEXT-style restart truth.

The original implementation follows below for audit/history only.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.employer_origin_gate_registry import OFFICIAL_EMPLOYER_ORIGIN_GATES
from src.search_intelligence.origin_url_policy import has_disallowed_source_url_shape

MISSING_CANDIDATE_URL_MARKERS = {"", "none", "null"}

EARLY_GATE_NAMES = tuple(
    gate.gate_name
    for gate in OFFICIAL_EMPLOYER_ORIGIN_GATES
    if gate.gate_order <= 7
)
DETAIL_EVIDENCE_GATE = "detail_evidence_gate"
RELEVANCE_GATE = "relevance_gate"
SOURCE_LIFECYCLE_GATE = "source_lifecycle_tracking"
TERMINAL_GATE_STATUSES = {"failed", "manual_review_required", "deferred"}
TERMINAL_GATE_DECISIONS = {"abort_documented", "manual_review_required"}


@dataclass(frozen=True)
class PersistedCandidate:
    candidate_id: int
    company_key: str
    company_name: str
    candidate_url: str
    source_name_candidate: str
    source_family_candidate: str
    source_target_candidate: str | None
    source_type_candidate: str
    status: str


@dataclass(frozen=True)
class PersistedGateReview:
    gate_name: str
    gate_status: str | None
    decision: str | None
    stop_reason: str | None


@dataclass(frozen=True)
class NextSafeCommand:
    action: str
    reason: str
    module: str | None = None
    args: tuple[str, ...] = ()


def load_candidate(conn: psycopg.Connection[Any], company_key: str) -> PersistedCandidate:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select
                id,
                company_key,
                company_name,
                candidate_url,
                source_name_candidate,
                source_family_candidate,
                source_target_candidate,
                source_type_candidate,
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

    return PersistedCandidate(
        candidate_id=int(row["id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        candidate_url=str(row["candidate_url"] or ""),
        source_name_candidate=str(row["source_name_candidate"]),
        source_family_candidate=str(row["source_family_candidate"]),
        source_target_candidate=row["source_target_candidate"],
        source_type_candidate=str(row["source_type_candidate"]),
        status=str(row["status"]),
    )


def load_gate_reviews(conn: psycopg.Connection[Any], candidate_id: int) -> dict[str, PersistedGateReview]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select distinct on (gate_name)
                gate_name,
                gate_status,
                decision,
                stop_reason
            from employer_origin_candidate_gate_reviews
            where candidate_id = %s
            order by gate_name, updated_at desc, id desc
            """,
            (candidate_id,),
        )
        rows = cur.fetchall()

    return {
        str(row["gate_name"]): PersistedGateReview(
            gate_name=str(row["gate_name"]),
            gate_status=row["gate_status"],
            decision=row["decision"],
            stop_reason=row["stop_reason"],
        )
        for row in rows
    }


def gate_passed(gates: dict[str, PersistedGateReview], gate_name: str) -> bool:
    gate = gates.get(gate_name)
    return bool(gate and gate.gate_status == "passed")


def has_usable_candidate_url(candidate: PersistedCandidate) -> bool:
    return candidate.candidate_url.strip().lower() not in MISSING_CANDIDATE_URL_MARKERS


def is_terminal_gate(gate: PersistedGateReview | None) -> bool:
    if gate is None:
        return False
    return (gate.gate_status or "") in TERMINAL_GATE_STATUSES or (gate.decision or "") in TERMINAL_GATE_DECISIONS


def terminal_stop_command(gate: PersistedGateReview) -> NextSafeCommand:
    decision = gate.decision or gate.gate_status or "blocked"
    reason = gate.stop_reason or "no stop reason recorded"
    return NextSafeCommand(
        action="no_safe_automated_action",
        reason=(
            f"{gate.gate_name} stopped with {decision}: {reason}; "
            "rerunning the same automated step would create a review loop"
        ),
    )


def source_discovery_stop_is_recoverable(candidate: PersistedCandidate, gate: PersistedGateReview | None) -> bool:
    if gate is None or gate.gate_name != "source_discovery":
        return False
    if (gate.decision or "") != "abort_documented":
        return False
    return has_disallowed_source_url_shape(candidate.candidate_url) is None




def technical_reachability_stop_is_recoverable(gate: PersistedGateReview | None) -> bool:
    if gate is None or gate.gate_name != "technical_reachability_gate":
        return False
    if (gate.decision or "") != "abort_documented":
        return False
    reason = (gate.stop_reason or "").lower()
    return "http 404" in reason or "not found" in reason or "request failed" in reason


def relevance_stop_is_recoverable(gate: PersistedGateReview | None) -> bool:
    if gate is None or gate.gate_name != RELEVANCE_GATE:
        return False
    if (gate.decision or "") != "manual_review_required":
        return False
    reason = (gate.stop_reason or "").lower()
    return (
        "bounded preview" in reason
        or "profile-term evidence" in reason
        or "target-location or remote" in reason
    )


def autonomous_relevance_discovery_args(
    candidate: PersistedCandidate,
    *,
    target_location: str,
    reviewed_by: str,
) -> tuple[str, ...]:
    return (
        "--company-key",
        candidate.company_key,
        "--target-location",
        target_location,
        "--reviewed-by",
        reviewed_by,
    )


def source_url_recovery_args(
    candidate: PersistedCandidate,
    *,
    target_location: str,
    reviewed_by: str,
) -> tuple[str, ...]:
    return (
        "--company-key",
        candidate.company_key,
        "--target-location",
        target_location,
        "--reviewed-by",
        reviewed_by,
        "--run-gate-review-after-recovery",
    )


def first_missing_early_gate(gates: dict[str, PersistedGateReview]) -> str | None:
    for gate_name in EARLY_GATE_NAMES:
        if not gate_passed(gates, gate_name):
            return gate_name
    return None


def initial_gate_args(
    candidate: PersistedCandidate,
    *,
    target_location: str,
    reviewed_by: str,
) -> tuple[str, ...]:
    return (
        "--company-key",
        candidate.company_key,
        "--company-name",
        candidate.company_name,
        "--candidate-url",
        candidate.candidate_url,
        "--source-name-candidate",
        candidate.source_name_candidate,
        "--source-family-candidate",
        candidate.source_family_candidate,
        "--source-target-candidate",
        candidate.source_target_candidate or target_location,
        "--source-type-candidate",
        candidate.source_type_candidate,
        "--target-location",
        target_location,
        "--reviewed-by",
        reviewed_by,
    )


def agent_chain_args(
    candidate: PersistedCandidate,
    *,
    target_location: str,
    reviewed_by: str,
    attempt_repair: bool = False,
) -> tuple[str, ...]:
    args = [
        "--company-key",
        candidate.company_key,
        "--target-location",
        target_location,
        "--reviewed-by",
        reviewed_by,
    ]
    if attempt_repair:
        args.append("--attempt-repair")
    return tuple(args)


def determine_next_safe_command(
    candidate: PersistedCandidate,
    gates: dict[str, PersistedGateReview],
    *,
    target_location: str,
    reviewed_by: str,
) -> NextSafeCommand:
    if candidate.status == "active_controlled" and gate_passed(gates, SOURCE_LIFECYCLE_GATE):
        return NextSafeCommand(
            action="monitor_existing_controlled_source",
            reason="source is active_controlled and lifecycle tracking is already passed",
        )

    if not has_usable_candidate_url(candidate):
        return NextSafeCommand(
            action="run_source_url_recovery",
            reason=(
                "candidate has no persisted source URL; run bounded source URL recovery "
                "before any gate review instead of passing a literal None/empty URL into the gate agent"
            ),
            module="scripts.run_employer_origin_source_url_recovery_agent",
            args=source_url_recovery_args(candidate, target_location=target_location, reviewed_by=reviewed_by),
        )

    missing_early_gate = first_missing_early_gate(gates)
    if missing_early_gate is not None:
        gate = gates.get(missing_early_gate)
        if gate is not None and is_terminal_gate(gate):
            if source_discovery_stop_is_recoverable(candidate, gate):
                return NextSafeCommand(
                    action="run_initial_gate_review",
                    reason=(
                        "source_discovery previously stopped, but the persisted candidate URL now passes "
                        "the shared URL-shape policy; rerun the bounded gate review"
                    ),
                    module="scripts.run_employer_origin_gate_agent",
                    args=initial_gate_args(candidate, target_location=target_location, reviewed_by=reviewed_by),
                )
            if technical_reachability_stop_is_recoverable(gate):
                return NextSafeCommand(
                    action="run_source_url_recovery",
                    reason=(
                        "technical_reachability stopped on the persisted URL; run bounded source URL "
                        "recovery before retrying the early gate review"
                    ),
                    module="scripts.run_employer_origin_source_url_recovery_agent",
                    args=source_url_recovery_args(candidate, target_location=target_location, reviewed_by=reviewed_by),
                )
            if relevance_stop_is_recoverable(gate):
                return NextSafeCommand(
                    action="run_autonomous_relevance_discovery",
                    reason=(
                        "relevance_gate stopped because the bounded listing preview did not expose enough evidence; "
                        "run autonomous job-detail discovery and signal learning before requiring manual review"
                    ),
                    module="scripts.run_employer_origin_autonomous_relevance_discovery_agent",
                    args=autonomous_relevance_discovery_args(candidate, target_location=target_location, reviewed_by=reviewed_by),
                )
            return terminal_stop_command(gate)
        return NextSafeCommand(
            action="run_initial_gate_review",
            reason=f"early gate {missing_early_gate!r} is not passed; detail repair would be premature",
            module="scripts.run_employer_origin_gate_agent",
            args=initial_gate_args(candidate, target_location=target_location, reviewed_by=reviewed_by),
        )

    detail_gate = gates.get(DETAIL_EVIDENCE_GATE)
    if not gate_passed(gates, DETAIL_EVIDENCE_GATE):
        if detail_gate is not None and is_terminal_gate(detail_gate):
            return terminal_stop_command(detail_gate)
        return NextSafeCommand(
            action="run_detail_evidence_repair",
            reason="early gates are passed but detail_evidence_gate is not passed",
            module="scripts.run_employer_origin_agent_chain",
            args=agent_chain_args(candidate, target_location=target_location, reviewed_by=reviewed_by, attempt_repair=True),
        )

    return NextSafeCommand(
        action="delegate_to_agent_chain",
        reason="early and detail-evidence gates are not the blocker; delegate to the canonical chain driver",
        module="scripts.run_employer_origin_agent_chain",
        args=agent_chain_args(candidate, target_location=target_location, reviewed_by=reviewed_by),
    )


def child_command(command: NextSafeCommand) -> list[str]:
    if command.module is None:
        return []
    return [sys.executable, "-m", command.module, *command.args]


def _emit_child_output(completed: subprocess.CompletedProcess[str]) -> None:
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)


def run_child(command: NextSafeCommand) -> int:
    actual = child_command(command)
    if not actual:
        return 0
    print("running:", " ".join(actual))
    completed = subprocess.run(actual, check=False, capture_output=True, text=True)
    _emit_child_output(completed)
    if completed.returncode != 0:
        print(
            f"child_command_failed: action={command.action} exit_code={completed.returncode} module={command.module}",
            file=sys.stderr,
        )
    return int(completed.returncode)


def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(**get_database_config()) as conn:
        candidate = load_candidate(conn, args.company_key)
        gates = load_gate_reviews(conn, candidate.candidate_id)

    command = determine_next_safe_command(
        candidate,
        gates,
        target_location=args.target_location,
        reviewed_by=args.reviewed_by,
    )

    print(f"candidate_id: {candidate.candidate_id}")
    print(f"candidate: {candidate.company_key} | {candidate.source_name_candidate}")
    print(f"next_safe_action: {command.action}")
    print(f"reason: {command.reason}")

    planned = child_command(command)
    if planned:
        print("planned_command:", " ".join(planned))

    if command.module is None:
        print(f"no_safe_automated_action: {command.reason}")
        print(f"next_safe_action_result: stopped action={command.action}")
        return 0

    if args.plan_only:
        return 0

    exit_code = run_child(command)
    if exit_code == 0:
        print(f"next_safe_action_result: completed action={command.action}")
    else:
        print(f"next_safe_action_result: failed action={command.action} exit_code={exit_code}", file=sys.stderr)
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the next safe employer-origin action for a persisted candidate. "
            "This prevents premature detail-evidence repair when early gates are still missing."
        )
    )
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--plan-only", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
