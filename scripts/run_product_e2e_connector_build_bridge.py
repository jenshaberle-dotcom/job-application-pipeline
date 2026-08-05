"""Run the Product E2E connector-build portfolio bridge.

Dry-run is the default. The runner reconstructs the current source-diverse
Golden-Path portfolio, evaluates every case blocked at ``connector_build`` through
the existing S6C approval-gated connector-build contract, and writes review
artifacts only. Build-request persistence requires exact targets and an exact
approval token. Connector artifact generation is never performed here.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row

from scripts.run_approval_gated_connector_build_agent import (
    ApprovalGatedConnectorBuildRepository,
    artifact_files_exist,
)
from scripts.run_origin_observation_seed_pool_agent import collect_seeds
from scripts.run_product_e2e_golden_path import SnapshotRepository
from src.config import get_database_config
from src.search_intelligence.approval_gated_connector_build import (
    ConnectorBuildRequest,
    evaluate_connector_build_request,
)
from src.search_intelligence.product_e2e_connector_build_bridge import (
    REQUEST_PERSISTENCE_APPROVAL_TOKEN,
    ConnectorBuildBridgePlan,
    build_connector_build_bridge_plan,
    parse_exact_target,
    select_exact_target_plans,
)
from src.search_intelligence.product_e2e_golden_path import (
    DiscoveryCase,
    LifecycleSnapshot,
    case_from_seed,
    select_representative_cases,
    trace_case,
)

PLAN_RESULT = "PRODUCT_E2E_CONNECTOR_BUILD_BRIDGE_PLAN_COMPLETED"
PERSIST_RESULT = "PRODUCT_E2E_CONNECTOR_BUILD_REQUEST_PERSISTENCE_COMPLETED"


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def collect_portfolio(
    conn: psycopg.Connection[Any],
    *,
    limit: int,
    limit_per_seed_source: int,
) -> tuple[list[DiscoveryCase], list[LifecycleSnapshot]]:
    seeds = collect_seeds(conn, limit_per_source=limit_per_seed_source)
    cases = select_representative_cases(
        (case_from_seed(seed) for seed in seeds),
        limit=limit,
    )
    snapshot_repository = SnapshotRepository(conn)
    snapshots = [snapshot_repository.load_snapshot(case) for case in cases]
    return cases, snapshots


def _evaluate_request(
    repository: ApprovalGatedConnectorBuildRepository,
    *,
    candidate_id: int,
    reviewed_by: str,
) -> ConnectorBuildRequest:
    candidate = repository.load_candidate(
        candidate_id=candidate_id,
        company_key=None,
    )
    gates = repository.load_gates(candidate.candidate_id)
    generation_plan = repository.load_generation_plan(candidate.candidate_id)
    learning_pressure = repository.load_learning_pressure(candidate.candidate_id)
    build_queue_evidence = repository.load_build_queue_evidence(candidate.candidate_id)

    preliminary = evaluate_connector_build_request(
        candidate=candidate,
        gates=gates,
        generation_plan=generation_plan,
        learning_pressure=learning_pressure,
        artifact_files_exist=False,
        approval_provided=False,
        reviewed_by=reviewed_by,
        build_queue_evidence=build_queue_evidence,
    )
    return evaluate_connector_build_request(
        candidate=candidate,
        gates=gates,
        generation_plan=generation_plan,
        learning_pressure=learning_pressure,
        artifact_files_exist=artifact_files_exist(preliminary),
        approval_provided=False,
        reviewed_by=reviewed_by,
        build_queue_evidence=build_queue_evidence,
    )


def build_current_plans(
    conn: psycopg.Connection[Any],
    *,
    cases: Iterable[DiscoveryCase],
    snapshots: Iterable[LifecycleSnapshot],
    reviewed_by: str,
) -> tuple[list[ConnectorBuildBridgePlan], dict[int, ConnectorBuildRequest]]:
    repository = ApprovalGatedConnectorBuildRepository(conn)
    plans: list[ConnectorBuildBridgePlan] = []
    requests: dict[int, ConnectorBuildRequest] = {}

    for case, snapshot in zip(cases, snapshots, strict=True):
        trace = trace_case(case, snapshot)
        if trace.next_blocker_stage != "connector_build":
            continue
        if snapshot.candidate_id is None:
            continue
        request = _evaluate_request(
            repository,
            candidate_id=snapshot.candidate_id,
            reviewed_by=reviewed_by,
        )
        plan = build_connector_build_bridge_plan(
            discovery_source_class=case.discovery_source_class,
            request=request,
        )
        plans.append(plan)
        requests[plan.candidate_id] = request

    return plans, requests


def _source_counts(plans: Iterable[ConnectorBuildBridgePlan]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for plan in plans:
        counts[plan.discovery_source_class] = (
            counts.get(plan.discovery_source_class, 0) + 1
        )
    return dict(sorted(counts.items()))


def _status_counts(plans: Iterable[ConnectorBuildBridgePlan]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for plan in plans:
        counts[plan.status] = counts.get(plan.status, 0) + 1
    return dict(sorted(counts.items()))


def write_report(
    *,
    run_dir: Path,
    cases: Iterable[DiscoveryCase],
    snapshots: Iterable[LifecycleSnapshot],
    all_plans: Iterable[ConnectorBuildBridgePlan],
    selected: Iterable[ConnectorBuildBridgePlan],
    requests: dict[int, ConnectorBuildRequest],
    persisted_candidate_ids: Iterable[int],
    persist_request: bool,
) -> Path:
    plans = tuple(all_plans)
    selected_plans = tuple(selected)
    persisted = set(persisted_candidate_ids)
    case_rows = []
    for case, snapshot in zip(cases, snapshots, strict=True):
        trace = trace_case(case, snapshot)
        case_rows.append(
            {
                "case": asdict(case),
                "snapshot": asdict(snapshot),
                "overall_status": trace.overall_status,
                "next_blocker_stage": trace.next_blocker_stage,
            }
        )

    payload = {
        "schema_version": "product_e2e_connector_build_bridge.v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "mode": "persist_request" if persist_request else "dry_run",
        "review_output_only_not_pipeline_input": True,
        "portfolio_cases": case_rows,
        "all_current_plans": [asdict(plan) for plan in plans],
        "selected_targets": [
            f"{plan.candidate_id}:{plan.company_key}" for plan in selected_plans
        ],
        "outcomes": [
            {
                "plan": asdict(plan),
                "request": requests[plan.candidate_id].as_dict(),
                "request_persisted": plan.candidate_id in persisted,
            }
            for plan in selected_plans
        ],
        "summary": {
            "portfolio_case_count": len(case_rows),
            "connector_blocker_count": len(plans),
            "selected_count": len(selected_plans),
            "persisted_request_count": len(persisted),
            "source_class_counts": _source_counts(plans),
            "status_counts": _status_counts(selected_plans),
            "provider_requests": 0,
            "llm_requests": 0,
        },
        "boundary": {
            "db_backed_golden_path_selection": True,
            "company_specific_branching": False,
            "dry_run_default": True,
            "exact_target_required_for_request_persistence": True,
            "exact_approval_token_required_for_request_persistence": True,
            "s6c_is_only_build_request_writer": True,
            "approval_provided_to_s6c": False,
            "connector_artifact_generation": False,
            "connector_registration": False,
            "source_activation": False,
            "bronze_silver_gold_job_mutation": False,
            "scheduler_or_wave_mutation": False,
            "assessment_ranking_top5_or_application_mutation": False,
            "provider_or_llm_request": False,
        },
    }
    path = run_dir / "result.json"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate fresh Product E2E connector-build blockers through the "
            "existing approval-gated S6C connector-build contract."
        )
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--limit-per-seed-source", type=int, default=100)
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="Exact target candidate_id:company_key.",
    )
    parser.add_argument("--persist-request", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    if args.limit < 1 or args.limit > 5:
        raise SystemExit("--limit must be between 1 and 5")
    if args.persist_request and not args.target:
        raise SystemExit(
            "--persist-request requires at least one exact --target "
            "candidate_id:company_key"
        )
    if (
        args.persist_request
        and args.approval_token != REQUEST_PERSISTENCE_APPROVAL_TOKEN
    ):
        raise SystemExit(
            "--persist-request requires --approval-token "
            f"{REQUEST_PERSISTENCE_APPROVAL_TOKEN}"
        )

    try:
        parsed_targets = [parse_exact_target(value) for value in args.target]
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    with connect() as conn:
        cases, snapshots = collect_portfolio(
            conn,
            limit=args.limit,
            limit_per_seed_source=args.limit_per_seed_source,
        )
        plans, requests = build_current_plans(
            conn,
            cases=cases,
            snapshots=snapshots,
            reviewed_by=args.reviewed_by,
        )
        try:
            selected = (
                select_exact_target_plans(
                    plans,
                    requested_targets=args.target,
                    require_request_persistence=args.persist_request,
                )
                if parsed_targets
                else tuple(plans)
            )
        except ValueError as exc:
            conn.rollback()
            raise SystemExit(str(exc)) from exc

        persisted_candidate_ids: list[int] = []
        if args.persist_request:
            repository = ApprovalGatedConnectorBuildRepository(conn)
            for plan in selected:
                repository.upsert_build_request(
                    requests[plan.candidate_id],
                    reviewed_by=args.reviewed_by,
                )
                persisted_candidate_ids.append(plan.candidate_id)
        else:
            conn.rollback()

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = args.output_dir / f"product_e2e_connector_build_bridge_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    report_path = write_report(
        run_dir=run_dir,
        cases=cases,
        snapshots=snapshots,
        all_plans=plans,
        selected=selected,
        requests=requests,
        persisted_candidate_ids=persisted_candidate_ids,
        persist_request=args.persist_request,
    )

    print("Product E2E generic connector-build bridge")
    print(f"mode: {'persist_request' if args.persist_request else 'dry_run'}")
    print(f"portfolio_cases: {len(cases)}/5")
    print(f"connector_blockers: {len(plans)}")
    print(f"source_classes: {json.dumps(_source_counts(plans), sort_keys=True)}")
    print("provider_requests: 0")
    print("llm_requests: 0")
    for plan in selected:
        print(
            "case: "
            f"source={plan.discovery_source_class} | "
            f"candidate_id={plan.candidate_id} | company={plan.company_name} | "
            f"status={plan.status} | blocker={plan.reason_code} | "
            f"build_status={plan.build_status} | mode={plan.build_mode} | "
            f"queue_action={plan.queue_action or '<none>'} | "
            "request_persistence_allowed="
            f"{str(plan.request_persistence_allowed).lower()} | "
            "request_persisted="
            f"{str(plan.candidate_id in persisted_candidate_ids).lower()}"
        )
    print(f"artifact_json: {report_path}")
    print(f"RESULT: {PERSIST_RESULT if args.persist_request else PLAN_RESULT}")
    return 0


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
