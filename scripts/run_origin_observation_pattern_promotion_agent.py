"""Promote adaptive origin-observation patterns into controlled strategy input.

This agent intentionally does not update candidate gates or candidate status. It
only classifies observed learning patterns as promoted/candidate/rejected so
later URL-finder and relevance-discovery agents can use promoted patterns.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.origin_pattern_promotion import (
    PROMOTION_BOUNDARY,
    ObservedPattern,
    PromotionDecision,
    promote_observed_pattern,
)


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def create_run(conn: psycopg.Connection[Any], *, run_label: str, reviewed_by: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO origin_pattern_promotion_runs (run_label, boundary, created_by)
            VALUES (%s, %s::jsonb, %s)
            RETURNING id
            """,
            (run_label, json.dumps(PROMOTION_BOUNDARY, sort_keys=True), reviewed_by),
        )
        run_id = int(cur.fetchone()["id"])
    conn.commit()
    return run_id


def load_patterns(conn: psycopg.Connection[Any], *, include_rejected: bool, limit: int) -> list[tuple[int, ObservedPattern]]:
    status_clause = "" if include_rejected else "WHERE promotion_status <> 'rejected'"
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, pattern_type, pattern_value, evidence_count, confidence, promotion_status
            FROM origin_observed_pattern_candidates
            {status_clause}
            ORDER BY updated_at DESC NULLS LAST, evidence_count DESC, id
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return [
        (
            int(row["id"]),
            ObservedPattern(
                pattern_type=str(row["pattern_type"]),
                pattern_value=str(row["pattern_value"]),
                evidence_count=int(row["evidence_count"]),
                confidence=float(row["confidence"]),
                current_status=str(row["promotion_status"]),
            ),
        )
        for row in rows
    ]


def persist_decision(
    cur: psycopg.Cursor[Any],
    *,
    run_id: int,
    pattern_id: int,
    pattern: ObservedPattern,
    decision: PromotionDecision,
    dry_run: bool,
) -> None:
    evidence = {
        "boundary": PROMOTION_BOUNDARY,
        "observed_evidence_count": pattern.evidence_count,
        "previous_status": pattern.current_status,
        "dry_run": dry_run,
        "decision": asdict(decision),
    }
    cur.execute(
        """
        INSERT INTO origin_pattern_promotion_decisions (
            run_id,
            observed_pattern_id,
            pattern_type,
            pattern_value,
            previous_status,
            promotion_status,
            confidence,
            signal_strength,
            pattern_category,
            usage_scope,
            usable_by_url_finder,
            usable_by_relevance_probe,
            reason,
            evidence
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            run_id,
            pattern_id,
            decision.pattern_type,
            decision.pattern_value,
            pattern.current_status,
            decision.promotion_status,
            decision.confidence,
            decision.signal_strength,
            decision.pattern_category,
            decision.usage_scope,
            decision.usable_by_url_finder,
            decision.usable_by_relevance_probe,
            decision.reason,
            json.dumps(evidence, sort_keys=True),
        ),
    )
    if dry_run:
        return
    cur.execute(
        """
        UPDATE origin_observed_pattern_candidates
        SET promotion_status = %s,
            confidence = GREATEST(confidence, %s),
            pattern_category = %s,
            usage_scope = %s,
            learning_notes = concat_ws(' ', nullif(learning_notes, ''), %s::text),
            evidence = evidence || %s::jsonb,
            updated_at = now()
        WHERE id = %s
        """,
        (
            decision.promotion_status,
            decision.confidence,
            decision.pattern_category,
            decision.usage_scope,
            f"A2D2 promotion taxonomy: {decision.reason}",
            json.dumps(
                {
                    "promotion": {
                        "status": decision.promotion_status,
                        "reason": decision.reason,
                        "usable_by_url_finder": decision.usable_by_url_finder,
                        "usable_by_relevance_probe": decision.usable_by_relevance_probe,
                        "signal_strength": decision.signal_strength,
                        "pattern_category": decision.pattern_category,
                        "usage_scope": decision.usage_scope,
                    }
                },
                sort_keys=True,
            ),
            pattern_id,
        ),
    )


def finish_run(conn: psycopg.Connection[Any], *, run_id: int, counts: dict[str, int]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE origin_pattern_promotion_runs
            SET promoted_count = %s,
                candidate_count = %s,
                rejected_count = %s,
                finished_at = now(),
                updated_at = now()
            WHERE id = %s
            """,
            (counts.get("promoted", 0), counts.get("candidate", 0), counts.get("rejected", 0), run_id),
        )
    conn.commit()


def run(args: argparse.Namespace) -> int:
    with connect() as conn:
        run_id = create_run(conn, run_label=args.run_label, reviewed_by=args.reviewed_by)
        patterns = load_patterns(conn, include_rejected=args.include_rejected, limit=args.limit)
        counts = {"promoted": 0, "candidate": 0, "rejected": 0}
        with conn.cursor() as cur:
            for pattern_id, pattern in patterns:
                decision = promote_observed_pattern(pattern, min_signal_evidence=args.min_signal_evidence)
                counts[decision.promotion_status] = counts.get(decision.promotion_status, 0) + 1
                persist_decision(
                    cur,
                    run_id=run_id,
                    pattern_id=pattern_id,
                    pattern=pattern,
                    decision=decision,
                    dry_run=args.dry_run,
                )
                print(
                    "promotion: "
                    f"{decision.pattern_type}={decision.pattern_value!r} | "
                    f"status={decision.promotion_status} | confidence={decision.confidence:.2f} | "
                    f"category={decision.pattern_category} | usage={decision.usage_scope} | "
                    f"url_finder={decision.usable_by_url_finder} | relevance={decision.usable_by_relevance_probe} | "
                    f"reason={decision.reason}"
                )
        conn.commit()
        finish_run(conn, run_id=run_id, counts=counts)

    print(f"promotion_run_id: {run_id}")
    print(f"promoted_count: {counts.get('promoted', 0)}")
    print(f"candidate_count: {counts.get('candidate', 0)}")
    print(f"rejected_count: {counts.get('rejected', 0)}")
    print(f"dry_run: {args.dry_run}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Promote observed origin-job patterns into controlled strategy input.")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--run-label", default="a2d-origin-pattern-promotion")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--min-signal-evidence", type=int, default=1)
    parser.add_argument("--include-rejected", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
