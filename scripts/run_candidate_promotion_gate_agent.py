"""Run the S7J Candidate Promotion Gate.

The agent promotes candidate-expansion review evidence into a reviewable
employer-origin candidate creation plan. Candidate creation is explicit and
bounded; connector registration, source activation, Bronze writes and scheduler
changes are never performed here.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.search_intelligence.candidate_promotion import (
    CandidateExpansionItem,
    CandidatePromotionItem,
    CandidatePromotionReview,
    build_candidate_promotion_review,
)


def db_connect() -> psycopg.Connection[Any]:
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "job_pipeline"),
        user=os.getenv("POSTGRES_USER", "job_user"),
        password=os.getenv("POSTGRES_PASSWORD", "job_password"),
        row_factory=dict_row,
    )


def resolve_review_id(conn: psycopg.Connection[Any], review_id: str) -> int:
    if review_id != "latest":
        return int(review_id)
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM candidate_expansion_reviews ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
    if row is None:
        raise SystemExit("No candidate_expansion_reviews rows found. Run S7I first.")
    return int(row["id"])


def load_expansion_items(conn: psycopg.Connection[Any], review_id: int) -> list[CandidateExpansionItem]:
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
              reason,
              evidence
            FROM candidate_expansion_review_items
            WHERE review_id = %s
            ORDER BY priority DESC, evidence_count DESC, company_name
            """,
            (review_id,),
        )
        rows = cur.fetchall()
    return [
        CandidateExpansionItem(
            item_id=int(row["id"]),
            review_id=int(row["review_id"]),
            company_key=str(row["company_key"]),
            company_name=str(row["company_name"]),
            source_name=str(row["source_name"]),
            decision=str(row["decision"]),
            priority=int(row["priority"]),
            evidence_count=int(row["evidence_count"]),
            known_candidate_id=row.get("known_candidate_id"),
            known_candidate_status=row.get("known_candidate_status"),
            recommended_next_action=str(row.get("recommended_next_action") or ""),
            reason=str(row.get("reason") or ""),
            evidence=dict(row.get("evidence") or {}),
        )
        for row in rows
    ]


def persist_review(
    conn: psycopg.Connection[Any],
    review: CandidatePromotionReview,
    *,
    reviewed_by: str,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO candidate_promotion_reviews (
                candidate_expansion_review_id,
                reviewed_by,
                item_count,
                promotion_recommended_count,
                manual_review_count,
                deferred_count,
                rejected_count,
                skipped_existing_count,
                created_candidate_count,
                boundary
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                review.candidate_expansion_review_id,
                reviewed_by,
                review.item_count,
                review.promotion_recommended_count,
                review.manual_review_count,
                review.deferred_count,
                review.rejected_count,
                review.skipped_existing_count,
                review.created_candidate_count,
                json.dumps(review.boundary),
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("candidate_promotion_reviews insert returned no id")
        promotion_review_id = int(row["id"])
        for item in review.items:
            persist_review_item(cur, promotion_review_id, item)
    conn.commit()
    return promotion_review_id


def persist_review_item(cur: psycopg.Cursor[Any], promotion_review_id: int, item: CandidatePromotionItem) -> None:
    cur.execute(
        """
        INSERT INTO candidate_promotion_review_items (
            promotion_review_id,
            candidate_expansion_item_id,
            candidate_expansion_review_id,
            company_key,
            company_name,
            source_name,
            source_decision,
            promotion_decision,
            priority,
            evidence_count,
            source_name_candidate,
            source_family_candidate,
            source_target_candidate,
            source_type_candidate,
            candidate_url,
            risk_level,
            reason,
            recommended_next_action,
            created_candidate_id,
            evidence
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            promotion_review_id,
            item.candidate_expansion_item_id,
            item.candidate_expansion_review_id,
            item.company_key,
            item.company_name,
            item.source_name,
            item.source_decision,
            item.promotion_decision,
            item.priority,
            item.evidence_count,
            item.source_name_candidate,
            item.source_family_candidate,
            item.source_target_candidate,
            item.source_type_candidate,
            item.candidate_url,
            item.risk_level,
            item.reason,
            item.recommended_next_action,
            item.created_candidate_id,
            json.dumps(item.evidence),
        ),
    )


def candidate_exists(conn: psycopg.Connection[Any], company_key: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM employer_origin_source_candidates WHERE company_key = %s LIMIT 1",
            (company_key,),
        )
        return cur.fetchone() is not None


def create_discovery_candidate(
    conn: psycopg.Connection[Any],
    item: CandidatePromotionItem,
    *,
    reviewed_by: str,
) -> int:
    if item.promotion_decision != "promotion_recommended":
        raise ValueError(f"Refusing to create candidate for decision={item.promotion_decision!r}")
    if candidate_exists(conn, item.company_key):
        raise ValueError(f"Candidate already exists for company_key={item.company_key!r}")
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
            ) VALUES (%s, %s, NULL, %s, %s, %s, %s, 'discovery', %s, %s, now())
            RETURNING id
            """,
            (
                item.company_key,
                item.company_name,
                item.source_name_candidate,
                item.source_family_candidate,
                item.source_target_candidate,
                item.source_type_candidate,
                item.risk_level,
                f"Created by S7J Candidate Promotion Gate from candidate_expansion_review_items.id={item.candidate_expansion_item_id}; reviewed_by={reviewed_by}.",
            ),
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("employer_origin_source_candidates insert returned no id")
    conn.commit()
    return int(row["id"])


def run(
    *,
    review_id_arg: str,
    company_key: str | None,
    reviewed_by: str,
    write_review: bool,
    create_candidates: bool,
    allow_batch_create: bool,
    max_create: int,
) -> dict[str, Any]:
    with db_connect() as conn:
        review_id = resolve_review_id(conn, review_id_arg)
        expansion_items = load_expansion_items(conn, review_id)
        review = build_candidate_promotion_review(
            expansion_items,
            candidate_expansion_review_id=review_id,
            company_key_filter=company_key,
        )

        created: list[tuple[str, int]] = []
        if create_candidates:
            if company_key is None and not allow_batch_create:
                raise SystemExit("--create-candidates requires --company-key or --allow-batch-create.")
            createable = [item for item in review.items if item.promotion_decision == "promotion_recommended"]
            if company_key is None:
                createable = createable[:max_create]
            for item in createable:
                candidate_id = create_discovery_candidate(conn, item, reviewed_by=reviewed_by)
                created.append((item.company_key, candidate_id))

        promotion_review_id: int | None = None
        if write_review:
            review_items = []
            created_by_key = {company_key: candidate_id for company_key, candidate_id in created}
            for item in review.items:
                if item.company_key in created_by_key:
                    review_items.append(
                        CandidatePromotionItem(
                            **{**item.__dict__, "created_candidate_id": created_by_key[item.company_key]}
                        )
                    )
                else:
                    review_items.append(item)
            review = CandidatePromotionReview(
                candidate_expansion_review_id=review.candidate_expansion_review_id,
                items=tuple(review_items),
                boundary=review.boundary,
            )
            promotion_review_id = persist_review(conn, review, reviewed_by=reviewed_by)

        return {
            "candidate_expansion_review_id": review_id,
            "promotion_review_id": promotion_review_id,
            "write_review": write_review,
            "create_candidates": create_candidates,
            "created_candidates": created,
            "review": review,
        }


def print_result(result: dict[str, Any]) -> None:
    review: CandidatePromotionReview = result["review"]
    print("S7J Candidate Promotion Gate")
    print("boundary: no browsing, no connector build, no connector registration, no source activation, no Bronze write, no scheduler change")
    print("---")
    print(f"candidate_expansion_review_id: {result['candidate_expansion_review_id']}")
    print(f"promotion_review_id: {result['promotion_review_id'] or '-'}")
    print(f"item_count: {review.item_count}")
    print(f"promotion_recommended_count: {review.promotion_recommended_count}")
    print(f"manual_review_count: {review.manual_review_count}")
    print(f"deferred_count: {review.deferred_count}")
    print(f"rejected_count: {review.rejected_count}")
    print(f"skipped_existing_count: {review.skipped_existing_count}")
    print(f"created_candidate_count: {review.created_candidate_count}")
    print(f"write_review: {result['write_review']}")
    print(f"create_candidates: {result['create_candidates']}")
    if result["created_candidates"]:
        print("created_candidates:")
        for company_key, candidate_id in result["created_candidates"]:
            print(f"- {company_key} -> candidate_id={candidate_id}")
    print("---")
    print("items:")
    for item in review.items[:40]:
        print(
            f"- {item.company_name} [{item.company_key}] | "
            f"promotion={item.promotion_decision} | source_decision={item.source_decision} | "
            f"priority={item.priority} | evidence={item.evidence_count} | next={item.recommended_next_action}"
        )
    if len(review.items) > 40:
        print(f"... {len(review.items) - 40} more items omitted")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run S7J Candidate Promotion Gate.")
    parser.add_argument("--review-id", default="latest", help="candidate_expansion_reviews.id or 'latest'.")
    parser.add_argument("--company-key", help="Limit review/promotion to one company_key.")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--write-review", action="store_true", help="Persist candidate promotion review rows.")
    parser.add_argument("--create-candidates", action="store_true", help="Create discovery-state employer-origin candidates. Explicitly gated.")
    parser.add_argument("--allow-batch-create", action="store_true", help="Allow --create-candidates without --company-key.")
    parser.add_argument("--max-create", type=int, default=5, help="Batch-create safety limit when --allow-batch-create is used.")
    args = parser.parse_args()

    result = run(
        review_id_arg=args.review_id,
        company_key=args.company_key,
        reviewed_by=args.reviewed_by,
        write_review=args.write_review,
        create_candidates=args.create_candidates,
        allow_batch_create=args.allow_batch_create,
        max_create=args.max_create,
    )
    print_result(result)


if __name__ == "__main__":
    main()
