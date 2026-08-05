"""Run the generic discovery-candidate to validated origin-URL bridge.

Dry-run is the default.  The runner selects DB-backed candidates, executes the
existing provider-free bounded origin repair, and delegates every persistence
plan/write to CAND-001.  Apply requires exact candidate-id/company-key targets and
an exact approval token.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

from psycopg.rows import dict_row

from scripts.run_cand001_validated_origin_url_persistence_gate import (
    connect,
    run as run_cand001,
)
from src.search_intelligence.product_e2e_origin_url_bridge import (
    APPROVAL_TOKEN,
    OriginUrlBridgePlan,
    build_origin_url_bridge_plan,
    candidate_from_row,
    parse_exact_target,
    select_exact_target_plans,
    select_source_diverse_plans,
)

PLAN_RESULT = "PRODUCT_E2E_ORIGIN_URL_BRIDGE_PLAN_COMPLETED"
APPLY_RESULT = "PRODUCT_E2E_ORIGIN_URL_BRIDGE_APPLY_COMPLETED"


def load_candidate_rows(
    *,
    target_ids: Iterable[int] = (),
    scan_limit: int = 100,
) -> list[dict[str, object]]:
    requested_ids = tuple(dict.fromkeys(int(value) for value in target_ids))
    with connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        if requested_ids:
            cur.execute(
                """
                SELECT id, company_key, company_name, status, candidate_url, notes
                FROM employer_origin_source_candidates
                WHERE id = ANY(%s)
                ORDER BY id
                """,
                (list(requested_ids),),
            )
        else:
            cur.execute(
                """
                SELECT id, company_key, company_name, status, candidate_url, notes
                FROM employer_origin_source_candidates
                WHERE notes LIKE '%%PRODUCT-E2E-INGRESS-001%%'
                ORDER BY updated_at DESC NULLS LAST, id DESC
                LIMIT %s
                """,
                (scan_limit,),
            )
        rows = [dict(row) for row in cur.fetchall()]
        conn.rollback()
    return rows


def build_current_plans(rows: Iterable[dict[str, object]]) -> list[OriginUrlBridgePlan]:
    return [build_origin_url_bridge_plan(candidate_from_row(row)) for row in rows]


def cand001_args(
    args: argparse.Namespace,
    *,
    selected: Iterable[OriginUrlBridgePlan],
    run_dir: Path,
) -> SimpleNamespace:
    return SimpleNamespace(
        benchmark_label=f"product_e2e_origin_url_bridge_{run_dir.name}",
        company_key=[plan.company_key for plan in selected],
        target_location=args.target_location,
        target_locale=args.target_locale,
        reviewed_by=args.reviewed_by,
        apply=args.apply,
        include_active_controlled=False,
        timeout_seconds=args.timeout_seconds,
        max_url_candidates=args.max_url_candidates,
        market_evidence_limit=args.market_evidence_limit,
        search_provider=["none"],
        search_query_limit=0,
        search_max_results=1,
        search_timeout_seconds=args.timeout_seconds,
        search_depth="basic",
        search_results_json=None,
        no_probe=False,
        max_evidence_candidates=args.max_evidence_candidates,
        max_evidence_http_requests=args.max_evidence_http_requests,
        evidence_timeout_seconds=args.timeout_seconds,
        max_response_bytes=args.max_response_bytes,
        llm_model="disabled",
        llm_reasoning_effort="low",
        llm_max_output_tokens=1,
        llm_reserved_input_tokens=1,
        llm_timeout_seconds=1.0,
        max_estimated_llm_cost_usd_per_company=0.0,
        disable_tavily=True,
        disable_llm=True,
        single_pass_diagnostic=False,
        output_json=run_dir / "cand001_result.json",
        output_markdown=run_dir / "cand001_result.md",
    )


def classify_cand001_item(item: dict[str, object]) -> tuple[str, str]:
    decision = str(item.get("decision") or "")
    if item.get("applied"):
        return "passed", "origin_url_persisted"
    if decision == "persist_validated_candidate_url":
        return "operator_decision_required", "validated_url_ready_for_exact_apply"
    if decision == "no_action_already_persisted":
        return "passed", "origin_url_already_persisted"
    if decision == "no_selected_url":
        return "valid_stop", "no_actionable_origin_evidence"
    if decision.startswith("manual_review_required"):
        return "operator_decision_required", decision
    if decision.startswith("skip_protected"):
        return "valid_stop", decision
    return "capability_gap", decision or "unclassified_cand001_outcome"


def write_bridge_report(
    *,
    run_dir: Path,
    all_plans: Iterable[OriginUrlBridgePlan],
    selected: Iterable[OriginUrlBridgePlan],
    cand_payload: dict[str, Any] | None,
    apply: bool,
) -> Path:
    selected_plans = tuple(selected)
    cand_items = {
        int(item["candidate_id"]): item
        for item in (cand_payload or {}).get("items", [])
        if isinstance(item, dict) and item.get("candidate_id") is not None
    }
    outcomes = []
    for plan in selected_plans:
        item = cand_items.get(plan.candidate_id)
        if item is None:
            status, reason_code = (
                ("passed", "origin_url_already_persisted")
                if plan.current_candidate_url
                else ("not_reached", "cand001_not_executed")
            )
        else:
            status, reason_code = classify_cand001_item(item)
        outcomes.append(
            {
                "candidate_id": plan.candidate_id,
                "company_key": plan.company_key,
                "company_name": plan.company_name,
                "discovery_source_class": plan.discovery_source_class,
                "bridge_action": plan.action,
                "status": status,
                "reason_code": reason_code,
                "cand001": item,
            }
        )
    payload = {
        "schema_version": "product_e2e_origin_url_bridge.v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "mode": "apply" if apply else "dry_run",
        "review_output_only_not_pipeline_input": True,
        "all_current_plans": [asdict(plan) for plan in all_plans],
        "selected_targets": [
            f"{plan.candidate_id}:{plan.company_key}" for plan in selected_plans
        ],
        "outcomes": outcomes,
        "summary": {
            "selected_count": len(selected_plans),
            "status_counts": {
                status: sum(1 for item in outcomes if item["status"] == status)
                for status in sorted({str(item["status"]) for item in outcomes})
            },
            "provider_requests": 0,
            "llm_requests": 0,
        },
        "boundary": {
            "db_backed_candidate_selection": True,
            "company_specific_branching": False,
            "tavily_disabled": True,
            "llm_disabled": True,
            "ordinary_bounded_http_probe_only": True,
            "cand001_is_only_url_writer": True,
            "exact_target_required_for_apply": True,
            "exact_approval_token_required_for_apply": True,
            "connector_generation_or_registration": False,
            "source_activation": False,
            "scheduler_or_wave_mutation": False,
            "bronze_silver_gold_or_product_assessment_mutation": False,
            "candidate_fact_or_fit_inference": False,
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
            "Bridge generic aggregator/public-job-API discovery candidates into "
            "the existing CAND-001 validated origin URL persistence gate."
        )
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="Exact target candidate_id:company_key. Required for Apply.",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--target-locale", default="de")
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--max-url-candidates", type=int, default=12)
    parser.add_argument("--market-evidence-limit", type=int, default=30)
    parser.add_argument("--max-evidence-candidates", type=int, default=4)
    parser.add_argument("--max-evidence-http-requests", type=int, default=12)
    parser.add_argument("--max-response-bytes", type=int, default=750_000)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    if args.limit < 1 or args.limit > 5:
        raise SystemExit("--limit must be between 1 and 5")
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit(f"--apply requires --approval-token {APPROVAL_TOKEN}")
    if args.apply and not args.target:
        raise SystemExit("--apply requires at least one exact --target candidate_id:company_key")

    try:
        parsed_targets = [parse_exact_target(value) for value in args.target]
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    rows = load_candidate_rows(
        target_ids=(candidate_id for candidate_id, _ in parsed_targets),
        scan_limit=max(50, args.limit * 20),
    )
    all_plans = build_current_plans(rows)
    try:
        selected = (
            select_exact_target_plans(all_plans, requested_targets=args.target)
            if args.target
            else select_source_diverse_plans(all_plans, limit=args.limit)
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = args.output_dir / f"product_e2e_origin_url_bridge_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)

    runnable = tuple(plan for plan in selected if plan.origin_discovery_allowed)
    cand_payload: dict[str, Any] | None = None
    if runnable:
        cand_payload = run_cand001(
            cand001_args(args, selected=runnable, run_dir=run_dir)
        )

    report_path = write_bridge_report(
        run_dir=run_dir,
        all_plans=all_plans,
        selected=selected,
        cand_payload=cand_payload,
        apply=args.apply,
    )
    print("Product E2E generic origin URL bridge")
    print(f"mode: {'apply' if args.apply else 'dry_run'}")
    print(f"selected_candidates: {len(selected)}")
    print("provider_requests: 0")
    print("llm_requests: 0")
    for plan in selected:
        item = next(
            (
                value
                for value in (cand_payload or {}).get("items", [])
                if isinstance(value, dict)
                and int(value.get("candidate_id") or -1) == plan.candidate_id
            ),
            None,
        )
        status, reason_code = (
            classify_cand001_item(item)
            if item is not None
            else ("passed", "origin_url_already_persisted")
        )
        print(
            "case: "
            f"source={plan.discovery_source_class} | candidate_id={plan.candidate_id} | "
            f"company={plan.company_name} | status={status} | blocker={reason_code} | "
            f"selected_url={(item or {}).get('selected_url') or '<none>'}"
        )
    print(f"artifact_json: {report_path}")
    print(f"RESULT: {APPLY_RESULT if args.apply else PLAN_RESULT}")
    return 0


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
