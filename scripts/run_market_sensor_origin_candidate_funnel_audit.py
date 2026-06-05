"""EO-001 Market Sensor -> Origin Candidate Funnel Audit.

This script quantifies how many market-observed companies enter the
employer-origin connector candidate funnel. It is schema-aware and read-only.
It intentionally does not create candidates, run gates, browse sources,
activate connectors, write Bronze/Silver data, or change scheduler state.
"""

from __future__ import annotations

import argparse
from typing import Any

from src.config import get_database_config
from src.search_intelligence.market_sensor_funnel import (
    ConnectorCandidate,
    MarketSensorItem,
    companies_without_connector_candidate,
    count_connector_companies_by_status,
    count_market_companies_by_decision,
    summarize_funnel,
)


def connect() -> Any:
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def table_exists(conn: Any, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) AS table_ref", (f"public.{table_name}",))
        row = cur.fetchone()
    return row is not None and row["table_ref"] is not None


def table_columns(conn: Any, table_name: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )
        return {str(row["column_name"]) for row in cur.fetchall()}


def require_tables(conn: Any) -> None:
    required = ["candidate_expansion_review_items", "employer_origin_source_candidates"]
    missing = [table_name for table_name in required if not table_exists(conn, table_name)]
    if missing:
        raise SystemExit(f"Missing required table(s): {', '.join(missing)}")


def load_market_sensor_items(conn: Any) -> list[MarketSensorItem]:
    columns = table_columns(conn, "candidate_expansion_review_items")
    required_columns = {
        "id",
        "company_key",
        "company_name",
        "source_name",
        "decision",
        "priority",
        "evidence_count",
    }
    missing = sorted(required_columns - columns)
    if missing:
        raise SystemExit("candidate_expansion_review_items is missing required column(s): " + ", ".join(missing))

    optional_selects = {
        "distinct_search_term_count": "distinct_search_term_count",
        "sample_title_count": "sample_title_count",
        "known_candidate_id": "known_candidate_id",
        "known_candidate_status": "known_candidate_status",
        "recommended_next_action": "recommended_next_action",
        "reason": "reason",
    }
    select_optional = [
        f"{column} AS {alias}" if column in columns else f"NULL AS {alias}"
        for alias, column in optional_selects.items()
    ]
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                id,
                company_key,
                company_name,
                source_name,
                decision,
                priority,
                evidence_count,
                {", ".join(select_optional)}
            FROM candidate_expansion_review_items
            ORDER BY priority DESC, evidence_count DESC, company_name, id
            """
        )
        rows = cur.fetchall()
    return [
        MarketSensorItem(
            item_id=int(row["id"]),
            company_key=str(row["company_key"]),
            company_name=str(row["company_name"]),
            source_name=str(row["source_name"]),
            decision=str(row["decision"]),
            priority=int(row["priority"] or 0),
            evidence_count=int(row["evidence_count"] or 0),
            distinct_search_term_count=int(row.get("distinct_search_term_count") or 0),
            sample_title_count=int(row.get("sample_title_count") or 0),
            known_candidate_id=None if row.get("known_candidate_id") is None else int(row["known_candidate_id"]),
            known_candidate_status=None if row.get("known_candidate_status") is None else str(row["known_candidate_status"]),
            recommended_next_action=str(row.get("recommended_next_action") or ""),
            reason=str(row.get("reason") or ""),
        )
        for row in rows
    ]


def load_connector_candidates(conn: Any) -> list[ConnectorCandidate]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, company_key, company_name, status, candidate_url
            FROM employer_origin_source_candidates
            ORDER BY company_key, id
            """
        )
        rows = cur.fetchall()
    return [
        ConnectorCandidate(
            candidate_id=int(row["id"]),
            company_key=str(row["company_key"]),
            company_name=str(row["company_name"]),
            status=str(row["status"]),
            candidate_url=None if row.get("candidate_url") is None else str(row["candidate_url"]),
        )
        for row in rows
    ]


def load_gate_progress_rows(conn: Any) -> list[dict[str, Any]]:
    if not table_exists(conn, "employer_origin_candidate_gate_reviews"):
        return []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                c.id,
                c.company_key,
                c.company_name,
                c.status,
                c.candidate_url,
                COUNT(gr.*) FILTER (WHERE gr.gate_status = 'passed') AS passed_gates,
                COUNT(gr.*) FILTER (WHERE gr.gate_status IN ('failed', 'manual_review_required')) AS review_or_failed_gates,
                COUNT(gr.*) FILTER (WHERE gr.gate_status = 'not_started') AS not_started_gates,
                COUNT(gr.*) AS recorded_gates
            FROM employer_origin_source_candidates c
            LEFT JOIN employer_origin_candidate_gate_reviews gr
              ON gr.candidate_id = c.id
            GROUP BY c.id, c.company_key, c.company_name, c.status, c.candidate_url
            ORDER BY passed_gates DESC, review_or_failed_gates DESC, c.company_key
            """
        )
        return [dict(row) for row in cur.fetchall()]


def load_promotion_rows(conn: Any) -> list[dict[str, Any]]:
    if not table_exists(conn, "candidate_promotion_review_items"):
        return []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                promotion_decision,
                COUNT(*) AS rows,
                COUNT(DISTINCT company_key) AS distinct_company_keys,
                MAX(created_at) AS latest_created_at
            FROM candidate_promotion_review_items
            GROUP BY promotion_decision
            ORDER BY rows DESC, promotion_decision
            """
        )
        return [dict(row) for row in cur.fetchall()]


def print_key_value(label: str, value: object) -> None:
    print(f"{label}: {value}")


def print_audit(limit: int) -> None:
    with connect() as conn:
        require_tables(conn)
        market_items = load_market_sensor_items(conn)
        connector_candidates = load_connector_candidates(conn)
        summary = summarize_funnel(market_items, connector_candidates)
        gaps = companies_without_connector_candidate(market_items, connector_candidates)

        print("EO-001 Market Sensor -> Origin Candidate Funnel Audit")
        print("boundary: read-only, no browsing, no candidate creation, no gate mutation, no connector build, no activation, no Bronze/Silver write, no scheduler change")
        print("---")
        print_key_value("market_sensor_review_items", len(market_items))
        print_key_value("market_sensor_companies", summary.market_sensor_companies)
        print_key_value("connector_candidate_companies", summary.connector_candidate_companies)
        print_key_value("with_connector_candidate", summary.with_connector_candidate)
        print_key_value("without_connector_candidate", summary.without_connector_candidate)
        print_key_value("connector_candidate_share_percent", f"{summary.connector_candidate_share_percent:.2f}")

        print("\nmarket_sensor_companies_by_decision:")
        for decision, count in count_market_companies_by_decision(market_items).items():
            print(f"- {decision}: {count}")

        print("\nconnector_candidate_companies_by_status:")
        for status, count in count_connector_companies_by_status(connector_candidates).items():
            print(f"- {status}: {count}")

        promotion_rows = load_promotion_rows(conn)
        if promotion_rows:
            print("\npromotion_review_items_by_decision:")
            for row in promotion_rows:
                print(
                    f"- {row['promotion_decision']}: rows={row['rows']} "
                    f"companies={row['distinct_company_keys']} latest={row['latest_created_at']}"
                )

        print(f"\nmarket_sensor_companies_without_connector_candidate_top_{limit}:")
        for gap in gaps[:limit]:
            print(
                "- "
                f"{gap.company_key} | {gap.company_name} | action={gap.suggested_funnel_action} | "
                f"items={gap.item_count} priority={gap.max_priority} evidence={gap.evidence_count} "
                f"terms={gap.distinct_search_term_count} titles={gap.sample_title_count} | "
                f"decisions={','.join(gap.decisions)}"
            )
            if gap.recommended_next_actions:
                print(f"  next_actions={'; '.join(gap.recommended_next_actions)}")

        print("\nconnector_candidates_with_gate_progress:")
        for row in load_gate_progress_rows(conn):
            print(
                "- "
                f"{row['company_key']} | status={row['status']} | passed={row['passed_gates']} "
                f"review_or_failed={row['review_or_failed_gates']} not_started={row['not_started_gates']} "
                f"recorded={row['recorded_gates']} | url={row['candidate_url'] or '<empty>'}"
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit market-sensor to employer-origin candidate funnel coverage.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of companies without connector candidates to print.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    print_audit(limit=args.limit)


if __name__ == "__main__":
    main()
