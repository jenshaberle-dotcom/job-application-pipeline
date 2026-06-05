"""EO-002 Market Sensor Candidate Promotion Batch.

Promote explicitly selected market-sensor companies into discovery-state
employer-origin source candidates. The batch is dry-run by default and creates
only candidate rows when --apply is passed. It does not browse, run gates,
build connectors, register/activate sources, write Bronze/Silver data, or
change scheduler state.
"""

from __future__ import annotations

import argparse
from typing import Any, Sequence

from src.config import get_database_config
from src.search_intelligence.market_sensor_candidate_promotion_batch import (
    CandidateCreationPlan,
    MarketSensorPromotionInput,
    PromotionBatchPlan,
    build_promotion_batch_plan,
    normalize_company_key,
)


def connect() -> Any:
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def resolve_review_id(conn: Any, review_id_arg: str) -> int:
    if review_id_arg != "latest":
        return int(review_id_arg)
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(review_id) AS review_id FROM candidate_expansion_review_items")
        row = cur.fetchone()
    if row is None or row["review_id"] is None:
        raise SystemExit("No candidate_expansion_review_items rows found.")
    return int(row["review_id"])


def load_market_sensor_items(
    conn: Any,
    *,
    review_id: int,
    company_keys: Sequence[str],
) -> list[MarketSensorPromotionInput]:
    requested_keys = [normalize_company_key(company_key) for company_key in company_keys]
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                review_id,
                company_key,
                company_name,
                source_name,
                decision,
                priority,
                evidence_count,
                known_candidate_id,
                known_candidate_status,
                recommended_next_action,
                reason
            FROM candidate_expansion_review_items
            WHERE review_id = %s
              AND lower(company_key) = ANY(%s)
            ORDER BY priority DESC, evidence_count DESC, company_name, id
            """,
            (review_id, requested_keys),
        )
        rows = cur.fetchall()
    return [
        MarketSensorPromotionInput(
            item_id=int(row["id"]),
            review_id=int(row["review_id"]),
            company_key=str(row["company_key"]),
            company_name=str(row["company_name"]),
            source_name=str(row["source_name"]),
            decision=str(row["decision"]),
            priority=int(row["priority"] or 0),
            evidence_count=int(row["evidence_count"] or 0),
            known_candidate_id=int(row["known_candidate_id"]) if row["known_candidate_id"] is not None else None,
            known_candidate_status=str(row["known_candidate_status"] or ""),
            recommended_next_action=str(row["recommended_next_action"] or ""),
            reason=str(row["reason"] or ""),
        )
        for row in rows
    ]


def load_existing_company_keys(conn: Any, *, company_keys: Sequence[str]) -> set[str]:
    requested_keys = [normalize_company_key(company_key) for company_key in company_keys]
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT lower(company_key) AS company_key
            FROM employer_origin_source_candidates
            WHERE lower(company_key) = ANY(%s)
            """,
            (requested_keys,),
        )
        return {str(row["company_key"]) for row in cur.fetchall()}


def create_candidate(conn: Any, plan: CandidateCreationPlan, *, reviewed_by: str, apply: bool) -> int | None:
    if not plan.create_allowed:
        raise ValueError(f"Refusing to create candidate for action={plan.action!r} company_key={plan.company_key!r}")
    if not apply:
        return None
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO employer_origin_source_candidates (
                company_key,
                company_name,
                candidate_url,
                source_name_candidate,
                source_family_candidate,
                source_target_candidate,
                source_type_candidate,
                status,
                risk_level,
                notes,
                updated_at
            ) VALUES (%s, %s, NULL, %s, %s, NULL, %s, 'discovery', %s, %s, now())
            RETURNING id
            """,
            (
                plan.company_key,
                plan.company_name,
                plan.source_name_candidate,
                plan.source_family_candidate,
                plan.source_type_candidate,
                plan.risk_level,
                (
                    "Created by EO-002 Market Sensor Candidate Promotion Batch "
                    f"from candidate_expansion_review_items.id={plan.item_id}; "
                    f"source_decision={plan.source_decision}; reviewed_by={reviewed_by}. "
                    "Candidate URL intentionally left NULL for Origin Source Discovery."
                ),
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("employer_origin_source_candidates insert returned no id")
    return int(row["id"])


def apply_creations(
    conn: Any,
    plan: PromotionBatchPlan,
    *,
    reviewed_by: str,
    apply: bool,
) -> PromotionBatchPlan:
    created_items: list[CandidateCreationPlan] = []
    for item in plan.items:
        if not item.create_allowed:
            created_items.append(item)
            continue
        candidate_id = create_candidate(conn, item, reviewed_by=reviewed_by, apply=apply)
        created_items.append(CandidateCreationPlan(**{**item.__dict__, "created_candidate_id": candidate_id}))
    if apply:
        conn.commit()
    return PromotionBatchPlan(
        requested_company_keys=plan.requested_company_keys,
        items=tuple(created_items),
        include_manual_review_required=plan.include_manual_review_required,
    )


def print_plan(plan: PromotionBatchPlan, *, review_id: int, apply: bool) -> None:
    print("EO-002 Market Sensor Candidate Promotion Batch")
    print(
        "boundary: dry-run first, explicit company keys only, no browsing, no gate mutation, "
        "no connector build, no registration, no activation, no Bronze/Silver write, no scheduler change"
    )
    print("---")
    print(f"candidate_expansion_review_id: {review_id}")
    print(f"requested_company_keys: {', '.join(plan.requested_company_keys)}")
    print(f"include_manual_review_required: {plan.include_manual_review_required}")
    print(f"apply: {apply}")
    print(f"planned_create_count: {plan.create_count}")
    print(f"blocked_or_skipped_count: {plan.blocked_count}")
    print(f"created_candidate_count: {plan.created_count}")
    print("---")
    print("plans:")
    for item in plan.items:
        created = f" created_candidate_id={item.created_candidate_id}" if item.created_candidate_id is not None else ""
        print(
            f"- {item.company_key} | {item.company_name or '<missing>'} | "
            f"decision={item.source_decision or '<missing>'} | action={item.action} | "
            f"create_allowed={item.create_allowed} | risk={item.risk_level or '-'} | reason={item.reason}{created}"
        )
    if not apply:
        print("dry_run: no candidate rows were created; pass --apply after review")
    elif plan.created_count:
        print("apply_complete: discovery candidates created; run Origin Source Discovery next")


def run(args: argparse.Namespace) -> int:
    if not args.company_key:
        raise SystemExit("At least one --company-key is required.")
    requested_keys = [normalize_company_key(company_key) for company_key in args.company_key]
    if len(set(requested_keys)) != len(requested_keys):
        raise SystemExit("Duplicate --company-key values are not allowed.")

    with connect() as conn:
        review_id = resolve_review_id(conn, args.review_id)
        items = load_market_sensor_items(conn, review_id=review_id, company_keys=requested_keys)
        existing_company_keys = load_existing_company_keys(conn, company_keys=requested_keys)
        plan = build_promotion_batch_plan(
            items,
            requested_company_keys=requested_keys,
            include_manual_review_required=args.include_manual_review_required,
            existing_company_keys=existing_company_keys,
        )
        if args.apply and any(item.action == "missing_market_sensor_item" for item in plan.items):
            raise SystemExit("ABORT: at least one requested company_key was not found in the selected review.")
        result = apply_creations(conn, plan, reviewed_by=args.reviewed_by, apply=args.apply)
    print_plan(result, review_id=review_id, apply=args.apply)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run EO-002 market sensor candidate promotion batch.")
    parser.add_argument("--review-id", default="latest", help="candidate_expansion_review_items.review_id or 'latest'.")
    parser.add_argument("--company-key", action="append", help="Company key to include. Repeat for a bounded batch.")
    parser.add_argument("--include-manual-review-required", action="store_true")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--apply", action="store_true", help="Actually create discovery candidates. Dry-run by default.")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
