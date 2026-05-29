from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row


REQUIRED_PASSED_GATES = (
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

DEFERRED_ACTIVATION_GATES = (
    "controlled_activation_gate",
    "bronze_validation",
    "silver_validation",
)


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
    candidate_url: str
    source_name_candidate: str
    source_family_candidate: str
    source_target_candidate: str | None
    source_type_candidate: str
    status: str
    risk_level: str


@dataclass(frozen=True)
class GateReview:
    gate_name: str
    gate_status: str
    decision: str
    stop_reason: str | None
    evidence: dict[str, Any]


@dataclass(frozen=True)
class ReadinessOutcome:
    status: str
    decision: str
    reason: str
    evidence: dict[str, Any]


def gate_passed(gates: dict[str, GateReview], gate_name: str) -> bool:
    gate = gates.get(gate_name)
    return bool(gate and gate.gate_status == "passed")


def gate_decision(gates: dict[str, GateReview], gate_name: str) -> str | None:
    gate = gates.get(gate_name)
    return gate.decision if gate else None


def missing_required_gates(gates: dict[str, GateReview]) -> list[str]:
    return [gate_name for gate_name in REQUIRED_PASSED_GATES if gate_name not in gates]


def unpassed_required_gates(gates: dict[str, GateReview]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for gate_name in REQUIRED_PASSED_GATES:
        gate = gates.get(gate_name)
        if gate is None:
            continue
        if gate.gate_status != "passed":
            result.append(
                {
                    "gate_name": gate_name,
                    "gate_status": gate.gate_status,
                    "decision": gate.decision,
                    "stop_reason": gate.stop_reason,
                }
            )
    return result


def open_manual_or_blocked_gates(gates: dict[str, GateReview]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for gate in gates.values():
        if gate.gate_name in DEFERRED_ACTIVATION_GATES:
            continue
        if gate.gate_status in {"manual_review_required", "blocked", "failed"}:
            result.append(
                {
                    "gate_name": gate.gate_name,
                    "gate_status": gate.gate_status,
                    "decision": gate.decision,
                    "stop_reason": gate.stop_reason,
                }
            )
    return sorted(result, key=lambda item: item["gate_name"])


def connector_candidate_spec(gates: dict[str, GateReview]) -> dict[str, Any]:
    gate = gates.get("connector_candidate_gate")
    if not gate:
        return {}
    evidence = gate.evidence or {}
    spec = evidence.get("connector_candidate_spec") or {}
    return spec if isinstance(spec, dict) else {}


def detail_url_count_from_spec(spec: dict[str, Any]) -> int:
    detail = spec.get("detail_evidence") or {}
    urls = detail.get("detail_urls") or []
    return len([url for url in urls if str(url).startswith(("http://", "https://"))])


def evaluate_readiness(candidate: SourceCandidate, gates: dict[str, GateReview]) -> ReadinessOutcome:
    evidence: dict[str, Any] = {
        "agent": "s3b_connector_build_readiness_agent",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "candidate": {
            "candidate_id": candidate.id,
            "company_key": candidate.company_key,
            "source_name_candidate": candidate.source_name_candidate,
            "source_type_candidate": candidate.source_type_candidate,
            "status": candidate.status,
            "risk_level": candidate.risk_level,
        },
        "required_passed_gates": list(REQUIRED_PASSED_GATES),
        "deferred_activation_gates": list(DEFERRED_ACTIVATION_GATES),
        "boundary": {
            "connector_generation_allowed": True,
            "connector_registration_allowed": False,
            "source_activation_allowed": False,
            "bronze_persistence_allowed": False,
            "recurring_ingestion_allowed": False,
            "csv_or_export_inputs_used": False,
        },
    }

    if candidate.status == "active_controlled":
        return ReadinessOutcome(
            status="not_applicable",
            decision="monitor_existing_source",
            reason="candidate is already active_controlled",
            evidence=evidence,
        )

    missing = missing_required_gates(gates)
    unpassed = unpassed_required_gates(gates)
    open_gates = open_manual_or_blocked_gates(gates)
    spec = connector_candidate_spec(gates)

    evidence.update(
        {
            "missing_required_gates": missing,
            "unpassed_required_gates": unpassed,
            "open_manual_or_blocked_gates": open_gates,
            "connector_candidate_spec_present": bool(spec),
            "detail_url_count": detail_url_count_from_spec(spec),
        }
    )

    if missing:
        return ReadinessOutcome(
            status="manual_review_required",
            decision="stop_before_connector_generation",
            reason="required gates are missing",
            evidence=evidence,
        )

    if unpassed or open_gates:
        return ReadinessOutcome(
            status="manual_review_required",
            decision="stop_before_connector_generation",
            reason="required gates are not all passed",
            evidence=evidence,
        )

    if gate_decision(gates, "connector_candidate_gate") != "build_connector_candidate":
        return ReadinessOutcome(
            status="manual_review_required",
            decision="stop_before_connector_generation",
            reason="connector_candidate_gate is not build_connector_candidate",
            evidence=evidence,
        )

    if not spec:
        return ReadinessOutcome(
            status="manual_review_required",
            decision="stop_before_connector_generation",
            reason="connector_candidate_spec is missing",
            evidence=evidence,
        )

    if detail_url_count_from_spec(spec) <= 0:
        return ReadinessOutcome(
            status="manual_review_required",
            decision="stop_before_connector_generation",
            reason="connector_candidate_spec has no concrete detail URLs",
            evidence=evidence,
        )

    return ReadinessOutcome(
        status="ready",
        decision="connector_generation_allowed_before_final_approval",
        reason="candidate has passed connector-build readiness checks",
        evidence=evidence,
    )


def outcome_lines(candidate: SourceCandidate, outcome: ReadinessOutcome) -> list[str]:
    lines = [
        f"candidate_id: {candidate.id}",
        f"candidate: {candidate.company_key} | {candidate.source_name_candidate}",
        f"connector_build_readiness: {outcome.status} / {outcome.decision}",
        f"reason: {outcome.reason}",
    ]

    if outcome.status == "ready":
        lines.append("NEXT: connector implementation may be generated, but registration and activation still require final approval.")
    else:
        lines.append("STOP: connector implementation is not allowed from the current DB gate state.")

    return lines


class ReadinessRepository:
    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def load_candidate(self, *, candidate_id: int | None, company_key: str | None) -> SourceCandidate:
        if candidate_id is None and not company_key:
            raise ValueError("Either candidate_id or company_key is required.")

        with self.conn.cursor(row_factory=dict_row) as cur:
            if candidate_id is not None:
                cur.execute(
                    """
                    select *
                    from employer_origin_source_candidates
                    where id = %s
                    """,
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
            company_name=str(row["company_name"]),
            candidate_url=str(row["candidate_url"]),
            source_name_candidate=str(row["source_name_candidate"]),
            source_family_candidate=str(row["source_family_candidate"]),
            source_target_candidate=row.get("source_target_candidate"),
            source_type_candidate=str(row["source_type_candidate"]),
            status=str(row["status"]),
            risk_level=str(row["risk_level"]),
        )

    def load_gates(self, candidate_id: int) -> dict[str, GateReview]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select gate_name, gate_status, decision, stop_reason, evidence
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


def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        repo = ReadinessRepository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=args.company_key)
        gates = repo.load_gates(candidate.id)

    outcome = evaluate_readiness(candidate, gates)
    for line in outcome_lines(candidate, outcome):
        print(line)

    if args.print_json:
        print(json.dumps(outcome.evidence, indent=2, ensure_ascii=False, default=str))

    return 0 if outcome.status in {"ready", "not_applicable"} else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate whether an employer-origin candidate is ready for connector generation before final approval."
    )
    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")
    parser.add_argument("--print-json", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
