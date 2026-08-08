"""Plan or explicitly backfill missing discovery provenance on legacy candidates.

Dry-run is the default. Apply is exact-target and may update only candidate notes
plus updated_at after revalidating the unresolved discovery-state row under lock.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from typing import Any, Iterable

import psycopg

from scripts.run_product_e2e_candidate_ingress import (
    collect_portfolio_cases,
    connect,
)
from src.search_intelligence.origin_seed_pool import normalize_company_key
from src.search_intelligence.product_e2e_candidate_ingress import (
    PROVENANCE_BACKFILL_APPROVAL_TOKEN,
    CandidateProvenanceBackfillPlan,
    ExistingCandidateProvenance,
    build_candidate_provenance_backfill_plan,
    select_provenance_backfill_plans,
)
from src.search_intelligence.product_e2e_golden_path import DiscoveryCase
from src.search_intelligence.product_e2e_origin_url_bridge import (
    discovery_source_class_from_notes,
)

PLAN_RESULT = "PRODUCT_E2E_CANDIDATE_PROVENANCE_BACKFILL_PLAN_COMPLETED"
APPLY_RESULT = "PRODUCT_E2E_CANDIDATE_PROVENANCE_BACKFILL_APPLY_COMPLETED"


def load_existing_candidate_provenance(
    conn: psycopg.Connection[Any],
    case: DiscoveryCase,
) -> ExistingCandidateProvenance | None:
    company_key = normalize_company_key(case.company_key or case.company_name)
    if not company_key:
        return None
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, company_key, company_name, status, candidate_url, notes
            FROM employer_origin_source_candidates
            WHERE lower(company_key) = lower(%s)
            ORDER BY updated_at DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (company_key,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    notes = str(row.get("notes") or "")
    return ExistingCandidateProvenance(
        candidate_id=int(row["id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        status=str(row["status"]),
        candidate_url=str(row.get("candidate_url") or "").strip() or None,
        discovery_source_class=discovery_source_class_from_notes(notes),
    )


def build_plans(
    conn: psycopg.Connection[Any],
    cases: Iterable[DiscoveryCase],
) -> list[CandidateProvenanceBackfillPlan]:
    return [
        build_candidate_provenance_backfill_plan(
            case,
            load_existing_candidate_provenance(conn, case),
        )
        for case in cases
    ]


def build_provenance_note(
    plan: CandidateProvenanceBackfillPlan,
    *,
    reviewed_by: str,
) -> str:
    return (
        "Provenance backfilled by PRODUCT-E2E-INGRESS-001; "
        f"discovery_source_class={plan.discovery_source_class}; "
        f"seed_type={plan.seed_type}; seed_source_table={plan.seed_source_table}; "
        f"case_id={plan.case_id}; reviewed_by={reviewed_by}. "
        "Existing candidate identity, lifecycle status and origin URL were not changed."
    )


def apply_one(
    conn: psycopg.Connection[Any],
    plan: CandidateProvenanceBackfillPlan,
    *,
    reviewed_by: str,
) -> bool:
    if not plan.backfill_allowed_after_explicit_approval:
        raise ValueError(f"Refusing provenance backfill for action={plan.action!r}.")
    if plan.candidate_id is None or not plan.company_key:
        raise ValueError("Refusing provenance backfill without exact candidate identity.")

    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (plan.company_key,))
        cur.execute(
            """
            SELECT id, company_key, company_name, status, candidate_url, notes
            FROM employer_origin_source_candidates
            WHERE id = %s
            FOR UPDATE
            """,
            (plan.candidate_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(f"Candidate {plan.candidate_id} disappeared before apply.")

        actual_key = normalize_company_key(str(row["company_key"]))
        if actual_key != plan.company_key:
            raise RuntimeError(
                f"Candidate {plan.candidate_id} company_key drifted to {actual_key!r}."
            )
        if str(row["status"]) != "discovery":
            raise RuntimeError(
                f"Candidate {plan.candidate_id} status drifted to {row['status']!r}."
            )
        if str(row.get("candidate_url") or "").strip():
            raise RuntimeError(
                f"Candidate {plan.candidate_id} acquired an origin URL before apply."
            )

        current_notes = str(row.get("notes") or "").strip()
        current_source_class = discovery_source_class_from_notes(current_notes)
        if current_source_class == plan.discovery_source_class:
            return False
        if current_source_class is not None:
            raise RuntimeError(
                f"Candidate {plan.candidate_id} provenance drifted to "
                f"{current_source_class!r}."
            )

        provenance_note = build_provenance_note(plan, reviewed_by=reviewed_by)
        updated_notes = f"{current_notes} {provenance_note}".strip()
        cur.execute(
            """
            UPDATE employer_origin_source_candidates
            SET notes = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (updated_notes, plan.candidate_id),
        )
        if cur.rowcount != 1:
            raise RuntimeError(
                f"Candidate {plan.candidate_id} provenance update affected {cur.rowcount} rows."
            )
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or explicitly backfill canonical discovery provenance on legacy "
            "employer-origin candidates."
        )
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--limit-per-seed-source", type=int, default=100)
    parser.add_argument("--manual-limit", type=int, default=50)
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="Exact candidate_id:company_key. Required for Apply.",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument("--print-json", action="store_true")
    return parser


def run(args: argparse.Namespace) -> int:
    if args.limit < 1 or args.limit > 5:
        raise SystemExit("--limit must be between 1 and 5")
    if args.apply and args.approval_token != PROVENANCE_BACKFILL_APPROVAL_TOKEN:
        raise SystemExit(
            "--apply requires --approval-token "
            f"{PROVENANCE_BACKFILL_APPROVAL_TOKEN}"
        )
    if args.apply and not args.target:
        raise SystemExit("--apply requires at least one exact --target candidate_id:company_key")

    with connect() as conn:
        if not args.apply:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SHOW transaction_read_only")
                transaction_read_only = str(cur.fetchone()["transaction_read_only"])
        else:
            transaction_read_only = "off"

        cases = collect_portfolio_cases(
            conn,
            limit=args.limit,
            limit_per_seed_source=args.limit_per_seed_source,
            manual_limit=args.manual_limit,
        )
        plans = build_plans(conn, cases)

        selected: tuple[CandidateProvenanceBackfillPlan, ...] = ()
        updated_ids: list[int] = []
        already_satisfied_ids: list[int] = []
        if args.apply:
            try:
                selected = select_provenance_backfill_plans(
                    plans,
                    requested_targets=args.target,
                )
            except ValueError as exc:
                conn.rollback()
                raise SystemExit(str(exc)) from exc
            for plan in selected:
                changed = apply_one(conn, plan, reviewed_by=args.reviewed_by)
                assert plan.candidate_id is not None
                if changed:
                    updated_ids.append(plan.candidate_id)
                else:
                    already_satisfied_ids.append(plan.candidate_id)
            conn.commit()
        else:
            conn.rollback()

    counts: dict[str, int] = {}
    for plan in plans:
        counts[plan.plan_status] = counts.get(plan.plan_status, 0) + 1

    payload = {
        "agent": "product_e2e_candidate_provenance_backfill",
        "mode": "apply" if args.apply else "dry_run",
        "transaction_read_only": transaction_read_only,
        "plan_status_counts": dict(sorted(counts.items())),
        "plans": [asdict(plan) for plan in plans],
        "selected_targets": [
            f"{plan.candidate_id}:{plan.company_key}" for plan in selected
        ],
        "updated_candidate_ids": updated_ids,
        "already_satisfied_candidate_ids": already_satisfied_ids,
        "boundary": {
            "candidate_creation": False,
            "candidate_notes_update": bool(args.apply),
            "candidate_url_update": False,
            "gate_mutation": False,
            "source_or_connector_mutation": False,
            "scheduler_or_wave_mutation": False,
            "bronze_silver_gold_or_product_v1_mutation": False,
            "ranking_or_application_action": False,
            "network_requests": False,
            "provider_or_llm_calls": False,
        },
        "result": APPLY_RESULT if args.apply else PLAN_RESULT,
    }

    print("Product E2E candidate provenance backfill")
    print(f"mode: {payload['mode']}")
    print(f"plan_status_counts: {json.dumps(payload['plan_status_counts'], sort_keys=True)}")
    for plan in plans:
        print(
            "plan: "
            f"source={plan.discovery_source_class} | "
            f"candidate_id={plan.candidate_id if plan.candidate_id is not None else '-'} | "
            f"company={plan.company_name or plan.company_key or '-'} | "
            f"action={plan.action} | status={plan.plan_status} | "
            "backfill_eligible="
            f"{str(plan.backfill_allowed_after_explicit_approval).lower()}"
        )
    if args.print_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    print(f"RESULT: {payload['result']}")
    return 0


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
