from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any

import psycopg


DEFAULT_GATES: tuple[tuple[int, str, bool], ...] = (
    (1, "company_candidate", False),
    (2, "source_discovery", True),
    (3, "risk_gate", True),
    (4, "technical_reachability_gate", True),
    (5, "scope_gate", True),
    (6, "defensive_preview_gate", True),
    (7, "relevance_gate", True),
    (8, "detail_evidence_gate", True),
    (9, "incremental_uniqueness_gate", True),
    (10, "connector_candidate_gate", True),
    (11, "controlled_activation_gate", True),
    (12, "bronze_validation", True),
    (13, "silver_validation", True),
    (14, "source_lifecycle_tracking", False),
)

VALID_GATE_NAMES = {name for _, name, _ in DEFAULT_GATES}

VALID_GATE_STATUSES = {
    "not_started",
    "passed",
    "failed",
    "deferred",
    "manual_review_required",
    "skipped",
    "not_applicable",
}

VALID_DECISIONS = {
    "continue",
    "defer",
    "manual_review_required",
    "abort_documented",
    "build_connector_candidate",
    "activate_controlled",
    "disable_or_deprecate",
    "connector_validation_failed",
    "ready_for_final_approval",
    "approval_blocked",
    "approval_token_required",
    "approve_connector_registration",
    "monitor_existing_source",
    "stop_before_connector_generation",
    "connector_generation_allowed_before_final_approval",
}


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


def parse_json_object(value: str | None) -> dict[str, Any]:
    if value in (None, ""):
        return {}

    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("JSON value must be an object.")
    return parsed


def validate_gate_update(gate_name: str, gate_status: str, decision: str, stop_reason: str | None) -> None:
    if gate_name not in VALID_GATE_NAMES:
        raise ValueError(f"Unsupported gate_name: {gate_name}")

    if gate_status not in VALID_GATE_STATUSES:
        raise ValueError(f"Unsupported gate_status: {gate_status}")

    if decision not in VALID_DECISIONS:
        raise ValueError(f"Unsupported decision: {decision}")

    if gate_status in {"failed", "deferred", "manual_review_required"} and not stop_reason:
        raise ValueError("stop_reason is required for failed, deferred and manual_review_required gates.")


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(DatabaseConfig.from_environment().dsn())


def create_candidate(conn: psycopg.Connection[Any], args: argparse.Namespace) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into employer_origin_source_candidates (
                company_key,
                company_name,
                candidate_url,
                source_name_candidate,
                source_family_candidate,
                source_target_candidate,
                source_type_candidate,
                status,
                risk_level,
                notes
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (company_key, candidate_url)
            do update set
                company_name = excluded.company_name,
                source_name_candidate = excluded.source_name_candidate,
                source_family_candidate = excluded.source_family_candidate,
                source_target_candidate = excluded.source_target_candidate,
                source_type_candidate = excluded.source_type_candidate,
                status = excluded.status,
                risk_level = excluded.risk_level,
                notes = excluded.notes,
                updated_at = now()
            returning id
            """,
            (
                args.company_key,
                args.company_name,
                args.candidate_url,
                args.source_name_candidate,
                args.source_family_candidate,
                args.source_target_candidate,
                args.source_type_candidate,
                args.status,
                args.risk_level,
                args.notes,
            ),
        )
        candidate_id = int(cur.fetchone()[0])

        for gate_order, gate_name, is_hard_gate in DEFAULT_GATES:
            cur.execute(
                """
                insert into employer_origin_candidate_gate_reviews (
                    candidate_id,
                    gate_name,
                    gate_order,
                    is_hard_gate
                )
                values (%s, %s, %s, %s)
                on conflict (candidate_id, gate_name)
                do nothing
                """,
                (candidate_id, gate_name, gate_order, is_hard_gate),
            )

        cur.execute(
            """
            insert into employer_origin_candidate_gate_events (
                candidate_id,
                event_type,
                new_state,
                event_reason,
                created_by
            )
            values (%s, 'candidate_created', %s::jsonb, %s, %s)
            """,
            (
                candidate_id,
                json.dumps(
                    {
                        "company_key": args.company_key,
                        "candidate_url": args.candidate_url,
                        "status": args.status,
                        "risk_level": args.risk_level,
                    },
                    ensure_ascii=False,
                ),
                "upsert candidate and initialize default gates",
                args.reviewed_by,
            ),
        )

    conn.commit()
    return candidate_id


def update_gate(conn: psycopg.Connection[Any], args: argparse.Namespace) -> int:
    validate_gate_update(args.gate_name, args.gate_status, args.decision, args.stop_reason)
    evidence = parse_json_object(args.evidence_json)

    with conn.cursor() as cur:
        cur.execute(
            """
            select id, gate_status, decision, stop_reason, evidence
            from employer_origin_candidate_gate_reviews
            where candidate_id = %s
              and gate_name = %s
            """,
            (args.candidate_id, args.gate_name),
        )
        previous = cur.fetchone()
        if previous is None:
            raise ValueError(
                f"No gate review exists for candidate_id={args.candidate_id} and gate_name={args.gate_name}."
            )

        previous_state = {
            "id": previous[0],
            "gate_status": previous[1],
            "decision": previous[2],
            "stop_reason": previous[3],
            "evidence": previous[4],
        }

        cur.execute(
            """
            update employer_origin_candidate_gate_reviews
            set
                gate_status = %s,
                decision = %s,
                stop_reason = %s,
                evidence = %s::jsonb,
                reviewed_at = now(),
                reviewed_by = %s,
                updated_at = now()
            where candidate_id = %s
              and gate_name = %s
            returning id
            """,
            (
                args.gate_status,
                args.decision,
                args.stop_reason,
                json.dumps(evidence, ensure_ascii=False),
                args.reviewed_by,
                args.candidate_id,
                args.gate_name,
            ),
        )
        gate_review_id = int(cur.fetchone()[0])

        cur.execute(
            """
            insert into employer_origin_candidate_gate_events (
                candidate_id,
                gate_review_id,
                event_type,
                previous_state,
                new_state,
                event_reason,
                created_by
            )
            values (%s, %s, 'gate_updated', %s::jsonb, %s::jsonb, %s, %s)
            """,
            (
                args.candidate_id,
                gate_review_id,
                json.dumps(previous_state, default=str, ensure_ascii=False),
                json.dumps(
                    {
                        "gate_name": args.gate_name,
                        "gate_status": args.gate_status,
                        "decision": args.decision,
                        "stop_reason": args.stop_reason,
                        "evidence": evidence,
                    },
                    ensure_ascii=False,
                ),
                args.event_reason,
                args.reviewed_by,
            ),
        )

    conn.commit()
    return gate_review_id


def list_candidates(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select
                c.id,
                c.company_key,
                c.company_name,
                c.source_name_candidate,
                c.status,
                c.risk_level,
                count(g.id) filter (where g.gate_status = 'passed') as passed_gates,
                count(g.id) filter (where g.gate_status in ('failed', 'deferred', 'manual_review_required')) as blocked_gates,
                count(g.id) as total_gates
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
            order by c.id
            """
        )
        return [
            {
                "id": row[0],
                "company_key": row[1],
                "company_name": row[2],
                "source_name_candidate": row[3],
                "status": row[4],
                "risk_level": row[5],
                "passed_gates": row[6],
                "blocked_gates": row[7],
                "total_gates": row[8],
            }
            for row in cur.fetchall()
        ]


def print_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("No employer-origin source candidates found.")
        return

    headers = list(rows[0].keys())
    widths = {
        header: max(len(header), *(len(str(row[header])) for row in rows))
        for header in headers
    }

    print(" | ".join(header.ljust(widths[header]) for header in headers))
    print("-+-".join("-" * widths[header] for header in headers))

    for row in rows:
        print(" | ".join(str(row[header]).ljust(widths[header]) for header in headers))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record DB-backed employer-origin connector gate reviews."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-candidate")
    create.add_argument("--company-key", required=True)
    create.add_argument("--company-name", required=True)
    create.add_argument("--candidate-url", required=True)
    create.add_argument("--source-name-candidate", required=True)
    create.add_argument("--source-family-candidate", required=True)
    create.add_argument("--source-target-candidate")
    create.add_argument(
        "--source-type-candidate",
        default="employer_origin_career_site",
        choices=[
            "employer_origin_career_site",
            "employer_origin_ats_backed_career_site",
        ],
    )
    create.add_argument(
        "--status",
        default="candidate",
        choices=[
            "candidate",
            "discovery",
            "deferred",
            "manual_review_required",
            "connector_candidate",
            "active_controlled",
            "watchlist",
            "degraded",
            "deprecated",
            "disabled",
            "abort_documented",
        ],
    )
    create.add_argument(
        "--risk-level",
        default="unknown",
        choices=["unknown", "low", "medium", "high", "blocked"],
    )
    create.add_argument("--notes")
    create.add_argument("--reviewed-by", default="manual")

    update = subparsers.add_parser("record-gate")
    update.add_argument("--candidate-id", type=int, required=True)
    update.add_argument("--gate-name", choices=sorted(VALID_GATE_NAMES), required=True)
    update.add_argument("--gate-status", choices=sorted(VALID_GATE_STATUSES), required=True)
    update.add_argument("--decision", choices=sorted(VALID_DECISIONS), required=True)
    update.add_argument("--stop-reason")
    update.add_argument("--evidence-json", default="{}")
    update.add_argument("--event-reason")
    update.add_argument("--reviewed-by", default="manual")

    subparsers.add_parser("list-candidates")

    return parser


def main() -> None:
    args = build_parser().parse_args()

    with connect() as conn:
        if args.command == "create-candidate":
            candidate_id = create_candidate(conn, args)
            print(f"candidate_id: {candidate_id}")
        elif args.command == "record-gate":
            gate_review_id = update_gate(conn, args)
            print(f"gate_review_id: {gate_review_id}")
        elif args.command == "list-candidates":
            print_table(list_candidates(conn))
        else:
            raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
