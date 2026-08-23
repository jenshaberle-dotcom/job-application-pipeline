from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import psycopg
from psycopg.rows import dict_row

if not __package__:  # direct ``python scripts/...`` execution
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from src.config import get_database_config
from src.search_intelligence.operator_review_label_diagnostics import (
    build_operator_review_label_diagnostics,
    canonical_diagnostics_payload,
    diagnostic_row_from_mapping,
    fingerprint_operator_review_label_diagnostics,
)


LABEL_TABLE = "job_review_relevance_label_events"
LABEL_VIEW = "gold_job_review_relevance_labels"


def _relation_exists(conn: psycopg.Connection[dict[str, object]], relation: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL AS exists", (f"public.{relation}",))
        row = cur.fetchone()
    return bool(row and row["exists"])


def load_operator_review_label_diagnostics() -> dict[str, object]:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")

            if not _relation_exists(conn, LABEL_TABLE) or not _relation_exists(conn, LABEL_VIEW):
                raise RuntimeError(
                    "operator review label diagnostics require migration 101 label table and Gold view"
                )

            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) AS event_count FROM {LABEL_TABLE}")  # noqa: S608 - fixed internal relation.
                event_row = cur.fetchone()
                historical_event_count = int(event_row["event_count"] if event_row else 0)

                cur.execute(
                    f"""
                    SELECT
                        label,
                        selection_reason,
                        deterministic_signal_visible,
                        ml_signal_visible,
                        llm_signal_visible,
                        reviewed_at
                    FROM {LABEL_VIEW}
                    ORDER BY silver_job_id
                    """  # noqa: S608 - fixed internal relation.
                )
                rows = [diagnostic_row_from_mapping(row) for row in cur.fetchall()]

    diagnostics = build_operator_review_label_diagnostics(
        rows,
        historical_event_count=historical_event_count,
    )
    payload = canonical_diagnostics_payload(diagnostics)
    payload["diagnostics_fingerprint"] = fingerprint_operator_review_label_diagnostics(
        diagnostics
    )
    payload["database_writes"] = 0
    payload["supervised_dataset_materialized"] = False
    payload["model_training_performed"] = False
    payload["provider_requests"] = 0
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report aggregate operator review label evidence without training or DB writes."
    )
    parser.add_argument("--pretty", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    payload = load_operator_review_label_diagnostics()
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
