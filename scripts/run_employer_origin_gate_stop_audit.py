"""Audit employer-origin gate stops and classify terminal vs recoverable stops."""

from __future__ import annotations

import argparse
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.gate_stop_classification import classify_gate_stop


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def run(args: argparse.Namespace) -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                c.id AS candidate_id,
                c.company_key,
                c.status AS candidate_status,
                c.candidate_url,
                gr.gate_name,
                gr.gate_status,
                gr.decision,
                gr.stop_reason,
                gr.evidence,
                gr.updated_at
            FROM employer_origin_source_candidates c
            JOIN employer_origin_candidate_gate_reviews gr
              ON gr.candidate_id = c.id
            WHERE
                gr.gate_status IN ('failed', 'manual_review_required')
                OR gr.decision IN ('abort_documented', 'manual_review_required')
            ORDER BY c.company_key, gr.gate_order NULLS LAST, gr.updated_at DESC NULLS LAST
            """
        )
        rows = cur.fetchall()

    if not rows:
        print("gate_stop_audit: no stop-like gate reviews found")
        return 0

    print("gate_stop_audit:")
    for row in rows:
        classification = classify_gate_stop(
            gate_name=str(row["gate_name"]),
            gate_status=row["gate_status"],
            decision=row["decision"],
            stop_reason=row["stop_reason"],
            evidence=row["evidence"],
        )
        if args.only_terminal and not classification.terminal:
            continue
        print(
            "gate_stop: "
            f"candidate_id={row['candidate_id']} "
            f"company_key={row['company_key']} "
            f"status={row['candidate_status']} "
            f"gate={row['gate_name']} "
            f"decision={row['decision']} "
            f"category={classification.category} "
            f"terminal={classification.terminal} "
            f"default_reprocess={classification.default_reprocess} "
            f"reason={row['stop_reason']}"
        )

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only-terminal", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
