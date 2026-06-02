"""Run the Search Intelligence nightly orchestrator foundation.

This command is intentionally not a scheduler hook yet. It assembles the current
Gold-backed Search Intelligence state, prints an ordered cycle report and, when
--write is explicitly provided, persists only the orchestrator run/step audit.
"""
from __future__ import annotations

import argparse
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from src.config import get_database_config
from src.search_intelligence.nightly_orchestrator import (
    ApprovalQueueItem,
    CandidateLifecycleItem,
    OriginDiscoveryItem,
    OrchestratorInput,
    OrchestratorPlan,
    build_orchestrator_plan,
    market_coverage_summary_from_row,
)


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _table_or_view_exists(conn: psycopg.Connection[Any], name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            select exists (
                select 1
                from information_schema.tables
                where table_schema = 'public'
                  and table_name = %s
            );
            """,
            (name,),
        )
        row = cur.fetchone()
        return bool(row and row["exists"])


def load_inputs(conn: psycopg.Connection[Any], *, limit: int) -> OrchestratorInput:
    with conn.cursor() as cur:
        cur.execute("select * from gold_market_coverage_summary;")
        summary = market_coverage_summary_from_row(cur.fetchone())

        cur.execute(
            """
            select
                company_key,
                display_company_name,
                current_stage,
                fn_pressure_level,
                blocking_gate,
                recommended_next_action
            from gold_candidate_lifecycle_status
            order by
                case current_stage
                    when 'build_approval_required' then 1
                    when 'gate_reassessment_required' then 2
                    when 'blocked_by_gate' then 3
                    when 'connector_artifact_generation_allowed' then 4
                    when 'active_controlled' then 5
                    else 9
                end,
                last_signal_at desc nulls last,
                display_company_name
            limit %s;
            """,
            (limit,),
        )
        lifecycle_items = tuple(CandidateLifecycleItem(**dict(row)) for row in cur.fetchall())

        cur.execute(
            """
            select
                approval_type,
                company_key,
                display_company_name,
                current_stage,
                recommendation
            from gold_approval_queue
            order by last_signal_at desc nulls last, display_company_name
            limit %s;
            """,
            (limit,),
        )
        approval_items = tuple(ApprovalQueueItem(**dict(row)) for row in cur.fetchall())

        origin_items: tuple[OriginDiscoveryItem, ...] = ()
        if _table_or_view_exists(conn, "gold_origin_source_discovery_status"):
            cur.execute(
                """
                select
                    company_key,
                    company_name,
                    discovery_status,
                    decision,
                    selected_origin_url,
                    blocker_code
                from gold_origin_source_discovery_status
                order by company_key
                limit %s;
                """,
                (limit,),
            )
            origin_items = tuple(OriginDiscoveryItem(**dict(row)) for row in cur.fetchall())

    return OrchestratorInput(
        summary=summary,
        lifecycle_items=lifecycle_items,
        approval_items=approval_items,
        origin_discovery_items=origin_items,
    )


def persist_plan(
    conn: psycopg.Connection[Any],
    *,
    plan: OrchestratorPlan,
    requested_by: str,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into search_intelligence_orchestrator_runs (
                cycle_name,
                run_mode,
                requested_by,
                status,
                completed_at,
                summary,
                guardrails
            ) values (%s, %s, %s, %s, now(), %s, %s)
            returning id;
            """,
            (
                plan.cycle_name,
                "write_audit_only",
                requested_by,
                plan.status,
                Json(plan.summary),
                Json(plan.guardrails),
            ),
        )
        run_id = int(cur.fetchone()["id"])
        for step in plan.steps:
            cur.execute(
                """
                insert into search_intelligence_orchestrator_steps (
                    run_id,
                    step_order,
                    step_name,
                    step_status,
                    action_mode,
                    recommendation,
                    reason,
                    metrics,
                    completed_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, now());
                """,
                (
                    run_id,
                    step.step_order,
                    step.step_name,
                    step.step_status,
                    step.action_mode,
                    step.recommendation,
                    step.reason,
                    Json(step.metrics),
                ),
            )
    conn.commit()
    return run_id


def print_plan(plan: OrchestratorPlan, *, persisted_run_id: int | None) -> None:
    print("S7F Nightly Search Intelligence Orchestrator")
    print("boundary: audit-only; no source activation, no connector registration, no Bronze write, no scheduler change")
    print("---")
    print(f"cycle_name: {plan.cycle_name}")
    print(f"status: {plan.status}")
    print(f"persisted_run_id: {persisted_run_id if persisted_run_id is not None else '-'}")
    print("guardrails:")
    for key, value in plan.guardrails.items():
        print(f"- {key}: {str(value).lower()}")
    print("---")
    print("summary:")
    for key, value in plan.summary.items():
        print(f"- {key}: {value}")
    print("---")
    print("steps:")
    for step in plan.steps:
        print(
            f"{step.step_order}. {step.step_name} | status={step.step_status} | "
            f"mode={step.action_mode}"
        )
        print(f"   recommendation: {step.recommendation}")
        print(f"   reason: {step.reason}")
        if step.metrics:
            metric_text = ", ".join(f"{key}={value}" for key, value in step.metrics.items())
            print(f"   metrics: {metric_text}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the S7F Search Intelligence nightly orchestrator foundation.")
    parser.add_argument("--reviewed-by", default="system", help="Reviewer/operator name written to audit runs.")
    parser.add_argument("--limit", type=int, default=25, help="Maximum Gold rows to load per review section.")
    parser.add_argument("--write", action="store_true", help="Persist orchestrator run and step audit only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with connect() as conn:
        inputs = load_inputs(conn, limit=args.limit)
        plan = build_orchestrator_plan(inputs)
        run_id = persist_plan(conn, plan=plan, requested_by=args.reviewed_by) if args.write else None
        print_plan(plan, persisted_run_id=run_id)
        if not args.write:
            print("---")
            print("NEXT: review the cycle report, then rerun with --write to persist the audit-only run.")


if __name__ == "__main__":
    main()
