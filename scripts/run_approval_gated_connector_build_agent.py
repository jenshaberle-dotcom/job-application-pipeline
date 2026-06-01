from __future__ import annotations

import argparse
import json
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_connector_artifact_generator import (
    SourceCandidate as ArtifactSourceCandidate,
    build_implementation,
    write_files,
)
from src.search_intelligence.approval_gated_connector_build import (
    ConnectorBuildRequest,
    GateReview,
    GenerationPlanState,
    LearningPressure,
    SourceCandidate,
    evaluate_connector_build_request,
)


class DatabaseConfig:
    @classmethod
    def dsn(cls) -> str:
        return (
            f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
            f"port={os.environ.get('POSTGRES_PORT', '5432')} "
            f"dbname={os.environ['POSTGRES_DB']} "
            f"user={os.environ['POSTGRES_USER']} "
            f"password={os.environ['POSTGRES_PASSWORD']}"
        )


class ApprovalGatedConnectorBuildRepository:
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
            candidate_id=int(row["id"]),
            company_key=str(row["company_key"]),
            company_name=str(row["company_name"]),
            candidate_url=str(row["candidate_url"]),
            source_name_candidate=str(row["source_name_candidate"]),
            source_family_candidate=str(row["source_family_candidate"]),
            source_target_candidate=row.get("source_target_candidate"),
            source_type_candidate=str(row["source_type_candidate"]),
            status=str(row["status"]),
            operational_risk_level=str(row["risk_level"]),
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

    def load_generation_plan(self, candidate_id: int) -> GenerationPlanState | None:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select generation_status, recommendation, updated_at::text as updated_at, evidence
                from employer_origin_connector_generation_plans
                where candidate_id = %s
                order by updated_at desc
                limit 1
                """,
                (candidate_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return GenerationPlanState(
            generation_status=str(row["generation_status"]),
            recommendation=str(row["recommendation"]),
            updated_at=row["updated_at"],
            evidence=dict(row["evidence"] or {}),
        )

    def load_learning_pressure(self, candidate_id: int) -> LearningPressure | None:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select status, risk_level, priority, trigger_reason, suggested_search_terms, updated_at::text as updated_at
                from candidate_reassessment_queue
                where candidate_id = %s
                  and status = 'open'
                order by priority desc, updated_at desc
                limit 1
                """,
                (candidate_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return LearningPressure(
            status=str(row["status"]),
            false_negative_risk_level=str(row["risk_level"]),
            priority=int(row["priority"]),
            trigger_reason=str(row["trigger_reason"]),
            suggested_search_terms=tuple(row["suggested_search_terms"] or ()),
            updated_at=row["updated_at"],
        )

    def upsert_build_request(self, request: ConnectorBuildRequest, *, reviewed_by: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                insert into employer_origin_connector_build_requests (
                    candidate_id,
                    build_status,
                    recommendation,
                    build_mode,
                    source_name_candidate,
                    source_type_candidate,
                    connector_module_path,
                    connector_test_path,
                    connector_docs_path,
                    next_command,
                    build_request,
                    boundary,
                    evidence,
                    reviewed_by,
                    updated_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, now())
                on conflict (candidate_id)
                do update set
                    build_status = excluded.build_status,
                    recommendation = excluded.recommendation,
                    build_mode = excluded.build_mode,
                    source_name_candidate = excluded.source_name_candidate,
                    source_type_candidate = excluded.source_type_candidate,
                    connector_module_path = excluded.connector_module_path,
                    connector_test_path = excluded.connector_test_path,
                    connector_docs_path = excluded.connector_docs_path,
                    next_command = excluded.next_command,
                    build_request = excluded.build_request,
                    boundary = excluded.boundary,
                    evidence = excluded.evidence,
                    reviewed_by = excluded.reviewed_by,
                    updated_at = now()
                """,
                (
                    request.candidate.candidate_id,
                    request.build_status,
                    request.recommendation,
                    request.build_mode,
                    request.candidate.source_name_candidate,
                    request.candidate.source_type_candidate,
                    request.paths.module_path,
                    request.paths.test_path,
                    request.paths.docs_path,
                    request.next_command,
                    json.dumps(request.as_dict(), ensure_ascii=False, default=str),
                    json.dumps(request.boundary, ensure_ascii=False),
                    json.dumps(request.evidence, ensure_ascii=False, default=str),
                    reviewed_by,
                ),
            )
        self.conn.commit()


def artifact_files_exist(request: ConnectorBuildRequest) -> bool:
    from pathlib import Path

    return all(Path(path).exists() for path in (request.paths.module_path, request.paths.test_path, request.paths.docs_path))


def build_artifact_candidate(candidate: SourceCandidate) -> ArtifactSourceCandidate:
    return ArtifactSourceCandidate(
        id=candidate.candidate_id,
        company_key=candidate.company_key,
        company_name=candidate.company_name,
        candidate_url=candidate.candidate_url,
        source_name_candidate=candidate.source_name_candidate,
        source_family_candidate=candidate.source_family_candidate,
        source_target_candidate=candidate.source_target_candidate,
        source_type_candidate=candidate.source_type_candidate,
        status=candidate.status,
        risk_level=candidate.operational_risk_level,
    )


def connector_spec_from_gates(gates: dict[str, GateReview]) -> dict[str, Any]:
    gate = gates.get("connector_candidate_gate")
    if not gate:
        return {}
    evidence = gate.evidence or {}
    spec = evidence.get("connector_candidate_spec") or {}
    return spec if isinstance(spec, dict) else {}


def fallback_investigation_spec(request: ConnectorBuildRequest) -> dict[str, Any]:
    return {
        "build_mode": request.build_mode,
        "recommended_connector": {
            "module_path": request.paths.module_path,
            "test_path": request.paths.test_path,
        },
        "detail_evidence": {
            "detail_urls": [],
            "fallback_reason": request.reason,
        },
        "boundary": {
            "bounded_investigation_connector": True,
            "registration_allowed": False,
            "source_activation_allowed": False,
            "bronze_persistence_allowed": False,
        },
    }


def write_connector_artifacts(request: ConnectorBuildRequest, gates: dict[str, GateReview], *, overwrite: bool) -> None:
    spec = connector_spec_from_gates(gates) or fallback_investigation_spec(request)
    synthetic_gate = {"evidence": {"connector_candidate_spec": spec}}
    implementation = build_implementation(build_artifact_candidate(request.candidate), synthetic_gate)
    write_files(implementation, overwrite=overwrite)


def print_request(request: ConnectorBuildRequest) -> None:
    print("S6C Approval-Gated Connector Build Agent")
    print(f"candidate_id: {request.candidate.candidate_id}")
    print(f"candidate: {request.candidate.company_key} | {request.candidate.source_name_candidate}")
    print(f"build_status: {request.build_status}")
    print(f"recommendation: {request.recommendation}")
    print(f"build_mode: {request.build_mode}")
    print(f"reason: {request.reason}")
    print(f"approval_required: {str(request.approval_required).lower()}")
    print(f"approval_provided: {str(request.approval_provided).lower()}")
    print(f"artifact_generation_allowed: {str(request.artifact_generation_allowed).lower()}")
    print(f"next_command: {request.next_command or '-'}")
    print("planned_artifacts:")
    print(f"- {request.paths.module_path}")
    print(f"- {request.paths.test_path}")
    print(f"- {request.paths.docs_path}")
    learning_pressure = request.evidence.get("learning_pressure", {})
    if learning_pressure.get("present"):
        print(f"false_negative_risk_level: {learning_pressure.get('false_negative_risk_level')}")
        print(f"learning_trigger_reason: {learning_pressure.get('trigger_reason')}")
    print("boundary: no auto-PR, no connector registration, no source activation, no Bronze write, no scheduler change")


def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.dsn()) as conn:
        repo = ApprovalGatedConnectorBuildRepository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=args.company_key)
        gates = repo.load_gates(candidate.candidate_id)
        generation_plan = repo.load_generation_plan(candidate.candidate_id)
        learning_pressure = repo.load_learning_pressure(candidate.candidate_id)

        preliminary = evaluate_connector_build_request(
            candidate=candidate,
            gates=gates,
            generation_plan=generation_plan,
            learning_pressure=learning_pressure,
            artifact_files_exist=False,
            approval_provided=args.approve_build,
            reviewed_by=args.reviewed_by,
        )
        request = evaluate_connector_build_request(
            candidate=candidate,
            gates=gates,
            generation_plan=generation_plan,
            learning_pressure=learning_pressure,
            artifact_files_exist=artifact_files_exist(preliminary),
            approval_provided=args.approve_build,
            reviewed_by=args.reviewed_by,
        )

        print_request(request)

        if args.write:
            repo.upsert_build_request(request, reviewed_by=args.reviewed_by)
            print("connector_build_request_upserted: true")

    if args.approve_build and request.artifact_generation_allowed:
        write_connector_artifacts(request, gates, overwrite=args.overwrite)
        print("connector_artifacts_written: true")
        print("NEXT: run connector validation. Registration still requires final approval.")
    elif request.next_command:
        print("NEXT: run the recommended command after review.")

    if args.print_json:
        print(json.dumps(request.as_dict(), indent=2, ensure_ascii=False, default=str))

    return 0 if request.build_status not in {"blocked"} else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or execute an approval-gated employer-origin connector artifact build."
    )
    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--approve-build", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
