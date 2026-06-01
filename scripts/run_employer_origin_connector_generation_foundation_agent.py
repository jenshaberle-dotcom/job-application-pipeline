from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.search_intelligence.employer_origin_connector_generation import (
    GateReassessmentSignal,
    GateReview,
    SourceCandidate,
    build_connector_generation_plan,
    default_connector_paths,
)


DEFAULT_OUTPUT_DIR = Path("exports/s6a_employer_origin_connector_generation_foundation")


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


class ConnectorGenerationRepository:
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
            candidate_id=int(row["id"]),
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

    def load_reassessment_signal(self, candidate_id: int) -> GateReassessmentSignal | None:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select
                    rq.status,
                    rq.risk_level,
                    rq.priority,
                    rq.trigger_reason,
                    rq.suggested_search_terms,
                    rq.updated_at::text as updated_at,
                    gate_state.latest_gate_reviewed_at::text as latest_gate_reviewed_at
                from candidate_reassessment_queue rq
                left join lateral (
                    select max(reviewed_at) as latest_gate_reviewed_at
                    from employer_origin_candidate_gate_reviews g
                    where g.candidate_id = rq.candidate_id
                ) gate_state on true
                where rq.candidate_id = %s
                  and rq.status = 'open'
                  and rq.updated_at > coalesce(gate_state.latest_gate_reviewed_at, '1970-01-01'::timestamptz)
                order by rq.priority desc, rq.updated_at desc
                limit 1
                """,
                (candidate_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return GateReassessmentSignal(
            status=str(row["status"]),
            false_negative_risk_level=str(row["risk_level"]),
            priority=int(row["priority"]),
            trigger_reason=str(row["trigger_reason"]),
            suggested_search_terms=tuple(row["suggested_search_terms"] or ()),
            updated_at=row["updated_at"],
            latest_gate_reviewed_at=row["latest_gate_reviewed_at"],
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

    def upsert_generation_plan(self, plan: Any, *, reviewed_by: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                insert into employer_origin_connector_generation_plans (
                    candidate_id,
                    generation_status,
                    recommendation,
                    source_name_candidate,
                    source_type_candidate,
                    connector_module_path,
                    connector_test_path,
                    connector_docs_path,
                    next_command,
                    plan,
                    boundary,
                    evidence,
                    reviewed_by,
                    updated_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, now())
                on conflict (candidate_id)
                do update set
                    generation_status = excluded.generation_status,
                    recommendation = excluded.recommendation,
                    source_name_candidate = excluded.source_name_candidate,
                    source_type_candidate = excluded.source_type_candidate,
                    connector_module_path = excluded.connector_module_path,
                    connector_test_path = excluded.connector_test_path,
                    connector_docs_path = excluded.connector_docs_path,
                    next_command = excluded.next_command,
                    plan = excluded.plan,
                    boundary = excluded.boundary,
                    evidence = excluded.evidence,
                    reviewed_by = excluded.reviewed_by,
                    updated_at = now()
                """,
                (
                    plan.candidate.candidate_id,
                    plan.generation_status,
                    plan.recommendation,
                    plan.candidate.source_name_candidate,
                    plan.candidate.source_type_candidate,
                    plan.connector_module_path,
                    plan.connector_test_path,
                    plan.connector_docs_path,
                    plan.next_command,
                    json.dumps(plan.as_dict(), ensure_ascii=False, default=str),
                    json.dumps(plan.boundary, ensure_ascii=False),
                    json.dumps(plan.evidence, ensure_ascii=False, default=str),
                    reviewed_by,
                ),
            )
        self.conn.commit()


def artifacts_exist_for_candidate(candidate: SourceCandidate) -> bool:
    paths = default_connector_paths(candidate)
    return all(Path(value).exists() for value in paths.values())


def render_markdown(plan: Any) -> str:
    learning_signal = plan.evidence.get("learning_reassessment_signal", {})
    suggested_terms = ", ".join(learning_signal.get("suggested_search_terms", [])) or "-"
    lines = [
        f"# S6A Employer-Origin Connector Generation Plan — {plan.candidate.company_key}",
        "",
        "## Boundary",
        "",
        "This is a DB-backed connector-generation planning artifact. It does not create an auto-PR, does not activate a source, does not write Bronze records and does not approve recurring ingestion.",
        "",
        "## Decision",
        "",
        f"- status: `{plan.generation_status}`",
        f"- recommendation: `{plan.recommendation}`",
        f"- reason: {plan.reason}",
        f"- source: `{plan.candidate.source_name_candidate}`",
        f"- source type: `{plan.candidate.source_type_candidate}`",
        f"- source role: `{plan.evidence.get('source_role', '-')}`",
        "",
        "## Learning Reassessment Signal",
        "",
        f"- status: `{learning_signal.get('status', 'none')}`",
        f"- gate reassessment required: `{str(learning_signal.get('gate_reassessment_required', False)).lower()}`",
        f"- false-negative risk level: `{learning_signal.get('false_negative_risk_level', '-')}`",
        f"- priority: `{learning_signal.get('priority', '-')}`",
        f"- reason: {learning_signal.get('trigger_reason', '-')}",
        f"- suggested search terms: `{suggested_terms}`",
        f"- updated at: `{learning_signal.get('updated_at', '-')}`",
        f"- latest gate reviewed at: `{learning_signal.get('latest_gate_reviewed_at', '-')}`",
        "",
        "## Planned Artifacts",
        "",
        f"- connector module: `{plan.connector_module_path or '-'}`",
        f"- connector tests: `{plan.connector_test_path or '-'}`",
        f"- connector documentation: `{plan.connector_docs_path or '-'}`",
        "",
        "## Next Command",
        "",
        "```bash",
        plan.next_command or "# no command; manual review required",
        "```",
        "",
        "## Build Steps",
        "",
    ]

    for step in plan.build_steps:
        lines.append(f"- `{step.get('step')}` — {step.get('status')}")

    lines.extend(
        [
            "",
            "## Guardrails",
            "",
        ]
    )
    for key, value in plan.boundary.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")

    lines.extend(
        [
            "",
            "## Evidence Summary",
            "",
            f"- required gates missing: `{json.dumps(plan.evidence.get('missing_required_gates', []), ensure_ascii=False)}`",
            f"- unpassed required gates: `{json.dumps(plan.evidence.get('unpassed_required_gates', []), ensure_ascii=False)}`",
            f"- concrete detail URLs: `{plan.evidence.get('detail_url_count', 0)}`",
            f"- artifact files already exist: `{str(plan.evidence.get('artifact_files_exist', False)).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)

def write_report(*, plan: Any, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    base = plan.candidate.company_key.replace("/", "_")
    json_path = output_dir / f"{base}_connector_generation_plan.json"
    md_path = output_dir / f"{base}_connector_generation_plan.md"

    json_path.write_text(json.dumps(plan.as_dict(), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(plan), encoding="utf-8")
    return json_path, md_path


def print_preview(plan: Any, *, write: bool) -> None:
    print("S6A Employer-Origin Connector Generation Foundation")
    print(f"candidate_id: {plan.candidate.candidate_id}")
    print(f"candidate: {plan.candidate.company_key} | {plan.candidate.source_name_candidate}")
    print(f"generation_status: {plan.generation_status}")
    print(f"recommendation: {plan.recommendation}")
    print(f"reason: {plan.reason}")
    learning_signal = plan.evidence.get("learning_reassessment_signal", {})
    print(f"next_command: {plan.next_command or '-'}")
    print(f"learning_reassessment: {learning_signal.get('status', 'none')}")
    print(f"gate_reassessment_required: {str(learning_signal.get('gate_reassessment_required', False)).lower()}")
    if learning_signal.get("false_negative_risk_level"):
        print(f"false_negative_risk_level: {learning_signal.get('false_negative_risk_level')}")
        print(f"learning_trigger_reason: {learning_signal.get('trigger_reason')}")
    print(f"write_mode: {str(write).lower()}")
    print("boundary: no auto-PR, no source activation, no Bronze write, no scheduler change")
    if not write:
        if plan.generation_status == "gate_reassessment_required":
            print("NEXT: rerun the recommended reassessment command, then rerun this S6A plan.")
        else:
            print("NEXT: rerun with --write after reviewing the generation plan.")


def run(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.dsn()) as conn:
        repo = ConnectorGenerationRepository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=args.company_key)
        gates = repo.load_gates(candidate.candidate_id)
        reassessment_signal = repo.load_reassessment_signal(candidate.candidate_id)
        plan = build_connector_generation_plan(
            candidate=candidate,
            gates=gates,
            artifacts_exist=artifacts_exist_for_candidate(candidate),
            reviewed_by=args.reviewed_by,
            reassessment_signal=reassessment_signal,
        )
        print_preview(plan, write=args.write)

        if args.write:
            repo.upsert_generation_plan(plan, reviewed_by=args.reviewed_by)
            print("connector_generation_plan_upserted: true")

    if args.report:
        json_path, md_path = write_report(plan=plan, output_dir=Path(args.output_dir))
        print("Exported review artifacts:")
        print(f"- {json_path}")
        print(f"- {md_path}")

    return 0 if plan.generation_status in {"ready", "already_generated", "not_applicable"} else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a DB-backed S6A connector-generation plan for an employer-origin source candidate."
    )
    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
