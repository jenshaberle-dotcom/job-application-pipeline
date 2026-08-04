from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.connector_autonomy import (
    A1_POLICY_KEY,
    LEGACY_APPROVAL_TOKEN,
    ConnectorAutonomyPolicy,
    authorize_connector_registration,
    policy_from_row,
)
from src.search_intelligence.employer_origin_gate_registry import gate_order

FINAL_APPROVAL_GATE = "final_approval_gate"
APPROVAL_TOKEN = LEGACY_APPROVAL_TOKEN


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
    return bool(
        gate
        and gate.gate_status == "passed"
        and gate.decision == "ready_for_final_approval"
    )


def evaluate_final_approval(
    *,
    candidate: SourceCandidate,
    gates: dict[str, GateReview],
    approval_token: str | None,
    approved_by: str,
    autonomy_policy: ConnectorAutonomyPolicy | None = None,
) -> ApprovalOutcome:
    validated = validation_ready(gates)
    authorization = authorize_connector_registration(
        validation_ready=validated,
        approval_token=approval_token,
        policy=autonomy_policy,
    )

    evidence = {
        "agent": "s4c_final_approval_gate_agent",
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
        "authorization": {
            "allowed": authorization.allowed,
            "mode": authorization.mode,
            "reason": authorization.reason,
            "policy_key": authorization.policy_key,
            "policy_version": authorization.policy_version,
            "standing_authorized_by": authorization.standing_authorized_by,
        },
        "boundary": {
            "connector_registration_allowed_after_this_gate": (
                candidate.status != "active_controlled"
            ),
            "controlled_activation_requires_exact_readiness": True,
            "allowed_activation_readiness": "activation_readiness_supported",
            "source_activation_allowed_by_this_gate": False,
            "bronze_persistence_allowed": False,
            "recurring_ingestion_allowed": False,
            "scheduler_mutation_allowed": False,
            "provider_requests_allowed": False,
            "ranking_mutation_allowed": False,
            "application_actions_allowed": False,
            "csv_or_export_inputs_used": False,
        },
    }

    if candidate.status == "active_controlled":
        evidence["authorization"] = {
            "allowed": False,
            "mode": "not_applicable_existing_source",
            "reason": "candidate is already active_controlled",
            "policy_key": authorization.policy_key,
            "policy_version": authorization.policy_version,
            "standing_authorized_by": authorization.standing_authorized_by,
        }
        return ApprovalOutcome(
            gate_status="not_applicable",
            decision="monitor_existing_source",
            stop_reason="candidate is already active_controlled",
            evidence=evidence,
        )

    if not validated:
        return ApprovalOutcome(
            gate_status="manual_review_required",
            decision="approval_blocked",
            stop_reason=authorization.reason,
            evidence=evidence,
        )

    if not authorization.allowed:
        return ApprovalOutcome(
            gate_status="manual_review_required",
            decision="approval_token_required",
            stop_reason=authorization.reason,
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
        f"authorization_mode: {outcome.evidence['authorization']['mode']}",
    ]
    if outcome.stop_reason:
        lines.append(f"STOP: {outcome.stop_reason}")
    else:
        lines.append(
            "NEXT: registration may proceed; controlled activation still requires "
            "exact activation_readiness_supported evidence."
        )
    return lines


class ApprovalRepository:
    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def load_candidate(
        self,
        *,
        candidate_id: int | None,
        company_key: str | None,
    ) -> SourceCandidate:
        if candidate_id is None and not company_key:
            raise ValueError("Either candidate_id or company_key is required.")

        with self.conn.cursor(row_factory=dict_row) as cur:
            if candidate_id is not None:
                cur.execute(
                    "select * from employer_origin_source_candidates where id = %s",
                    (candidate_id,),
                )
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

    def load_autonomy_policy(self) -> ConnectorAutonomyPolicy | None:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "select to_regclass('public.connector_autonomy_policies') as relation"
            )
            relation = cur.fetchone()
            if relation is None or relation["relation"] is None:
                return None
            cur.execute(
                """
                select *
                from connector_autonomy_policies
                where policy_key = %s
                """,
                (A1_POLICY_KEY,),
            )
            row = cur.fetchone()
        return policy_from_row(row)

    def record_gate(
        self,
        *,
        candidate: SourceCandidate,
        outcome: ApprovalOutcome,
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
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (candidate_id, gate_name)
                do update set
                    gate_status = excluded.gate_status,
                    decision = excluded.decision,
                    stop_reason = excluded.stop_reason,
                    evidence = excluded.evidence,
                    reviewed_by = excluded.reviewed_by
                """,
                (
                    candidate.id,
                    gate_order(FINAL_APPROVAL_GATE),
                    FINAL_APPROVAL_GATE,
                    outcome.gate_status,
                    outcome.decision,
                    outcome.stop_reason,
                    json.dumps(outcome.evidence),
                    outcome.evidence["approved_by"],
                ),
            )
            cur.execute(
                "select to_regclass('public.connector_autonomy_authorization_events')"
            )
            relation = cur.fetchone()
            if relation and relation[0] is not None and outcome.gate_status != "not_applicable":
                authorization = outcome.evidence["authorization"]
                decision = (
                    "allowed"
                    if outcome.gate_status == "passed"
                    else "manual_review_required"
                )
                cur.execute(
                    """
                    insert into connector_autonomy_authorization_events (
                        candidate_id,
                        source_name_candidate,
                        action,
                        decision,
                        authorization_mode,
                        policy_key,
                        policy_version,
                        evidence,
                        recorded_by
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        candidate.id,
                        candidate.source_name_candidate,
                        "connector_registration",
                        decision,
                        authorization["mode"],
                        authorization["policy_key"],
                        authorization["policy_version"],
                        json.dumps(outcome.evidence),
                        outcome.evidence["approved_by"],
                    ),
                )


def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(**get_database_config()) as conn:
        repo = ApprovalRepository(conn)
        candidate = repo.load_candidate(
            candidate_id=args.candidate_id,
            company_key=args.company_key,
        )
        gates = repo.load_gates(candidate.id)
        autonomy_policy = repo.load_autonomy_policy()
        outcome = evaluate_final_approval(
            candidate=candidate,
            gates=gates,
            approval_token=args.approval_token,
            approved_by=args.approved_by,
            autonomy_policy=autonomy_policy,
        )

        if not args.dry_run:
            repo.record_gate(candidate=candidate, outcome=outcome)
            conn.commit()

    for line in approval_lines(candidate, outcome):
        print(line)

    if args.dry_run:
        print("DRY RUN: no DB gate state was changed.")

    if args.print_json:
        print(json.dumps(outcome.evidence, indent=2, ensure_ascii=False, default=str))

    return 0 if outcome.gate_status in {"passed", "not_applicable"} else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Record final connector-registration approval through the exact legacy "
            "token or the active validated-connector A1 policy."
        )
    )
    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")
    parser.add_argument("--approval-token")
    parser.add_argument("--approved-by", default="connector_autonomy_a1")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
