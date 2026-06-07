from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.run_origin_source_discovery_agent import run_for_company
from src.config import get_database_config
from src.search_intelligence.cand001_validated_origin_url_persistence import (
    CandidatePersistenceSnapshot,
    OriginUrlValidationEvidence,
    build_persistence_plan_item,
    evidence_from_origin_discovery_payload,
    markdown_report,
    report_payload,
)

DEFAULT_OUTPUT_DIR = Path("exports/cand001_validated_origin_url_persistence_gate")
REVIEW_TABLE = "candidate_origin_url_persistence_reviews"


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _db_object_exists(conn: psycopg.Connection[Any], object_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("select to_regclass(%s)", (object_name,))
        row = cur.fetchone()
    return bool(row and row["to_regclass"])


def load_candidate(conn: psycopg.Connection[Any], company_key: str) -> CandidatePersistenceSnapshot:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, company_key, company_name, status, candidate_url, risk_level
            FROM employer_origin_source_candidates
            WHERE company_key = %s
            ORDER BY updated_at DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (company_key,),
        )
        row = cur.fetchone()
    if not row:
        raise SystemExit(f"No employer-origin candidate found for company_key={company_key!r}.")
    return CandidatePersistenceSnapshot(
        candidate_id=int(row["id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        status=str(row["status"]),
        candidate_url=row["candidate_url"],
        risk_level=row["risk_level"],
    )


def duplicate_selected_url_exists(conn: psycopg.Connection[Any], *, candidate: CandidatePersistenceSnapshot, selected_url: str | None) -> bool:
    if not selected_url:
        return False
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT 1
            FROM employer_origin_source_candidates
            WHERE company_key = %s
              AND candidate_url = %s
              AND id <> %s
            LIMIT 1
            """,
            (candidate.company_key, selected_url, candidate.candidate_id),
        )
        return cur.fetchone() is not None


def write_review_and_candidate_url(
    conn: psycopg.Connection[Any],
    *,
    item,
    evidence: OriginUrlValidationEvidence,
    reviewed_by: str,
) -> int:
    if not _db_object_exists(conn, REVIEW_TABLE):
        raise SystemExit(
            f"Missing {REVIEW_TABLE}. Apply database migrations before running CAND-001 with --apply."
        )
    if not item.apply_allowed or not item.selected_url:
        raise SystemExit(f"Apply blocked for {item.company_key}: {item.decision}")

    boundary = {
        "sz1_candidate_metadata_transition": True,
        "explicit_apply_required": True,
        "no_gate_write": True,
        "no_evidence_write": True,
        "no_connector_registration": True,
        "no_source_activation": True,
        "no_scheduler_change": True,
    }
    evidence_payload = {
        "selected_url_source": item.selected_url_source,
        "url_finder_tier": item.url_finder_tier,
        "url_finder_decision": item.url_finder_decision,
        "confidence_score": item.confidence_score,
        "reason": evidence.reason,
        "risk_level": evidence.risk_level,
    }
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO candidate_origin_url_persistence_reviews (
                candidate_id,
                company_key,
                company_name,
                previous_candidate_url,
                selected_candidate_url,
                selected_url_source,
                decision,
                review_status,
                reason,
                boundary,
                evidence,
                reviewed_by,
                applied_at
            )
            VALUES (
                %(candidate_id)s,
                %(company_key)s,
                %(company_name)s,
                %(previous_candidate_url)s,
                %(selected_url)s,
                %(selected_url_source)s,
                %(decision)s,
                'applied',
                %(reason)s,
                %(boundary)s::jsonb,
                %(evidence)s::jsonb,
                %(reviewed_by)s,
                now()
            )
            RETURNING id
            """,
            {
                "candidate_id": item.candidate_id,
                "company_key": item.company_key,
                "company_name": item.company_name,
                "previous_candidate_url": item.previous_candidate_url,
                "selected_url": item.selected_url,
                "selected_url_source": item.selected_url_source,
                "decision": item.decision,
                "reason": item.reason,
                "boundary": json.dumps(boundary),
                "evidence": json.dumps(evidence_payload),
                "reviewed_by": reviewed_by,
            },
        )
        review_id = int(cur.fetchone()["id"])
        cur.execute(
            """
            UPDATE employer_origin_source_candidates
            SET candidate_url = %s,
                updated_at = now()
            WHERE id = %s
              AND (candidate_url IS NULL OR btrim(candidate_url) = '')
              AND status <> 'active_controlled'
            """,
            (item.selected_url, item.candidate_id),
        )
        if cur.rowcount != 1:
            raise SystemExit(
                f"Candidate URL write did not update exactly one row for {item.company_key}; transaction will abort."
            )
    return review_id


def origin_args_from_cli(args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        target_location=args.target_location,
        reviewed_by=args.reviewed_by,
        timeout_seconds=args.timeout_seconds,
        max_candidates=args.max_url_candidates,
        market_evidence_limit=args.market_evidence_limit,
        search_provider=args.search_provider,
        search_query_limit=args.search_query_limit,
        search_max_results=args.search_max_results,
        search_timeout_seconds=args.search_timeout_seconds,
        search_depth=args.search_depth,
        search_results_json=args.search_results_json,
        no_probe=args.no_probe,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    origin_args = origin_args_from_cli(args)
    items = []

    with connect() as conn:
        for company_key in args.company_key:
            candidate = load_candidate(conn, company_key)
            payload = run_for_company(origin_args, company_key)
            evidence = evidence_from_origin_discovery_payload(payload)
            duplicate_exists = duplicate_selected_url_exists(conn, candidate=candidate, selected_url=evidence.selected_url)
            planned = build_persistence_plan_item(
                candidate,
                evidence,
                include_active_controlled=args.include_active_controlled,
                duplicate_selected_url_exists=duplicate_exists,
            )
            if args.apply and planned.apply_allowed:
                review_id = write_review_and_candidate_url(conn, item=planned, evidence=evidence, reviewed_by=args.reviewed_by)
                planned = build_persistence_plan_item(
                    candidate,
                    evidence,
                    include_active_controlled=args.include_active_controlled,
                    duplicate_selected_url_exists=duplicate_exists,
                    applied=True,
                    audit_review_id=review_id,
                )
                print(f"candidate_url_applied: company_key={company_key} url={planned.selected_url} review_id={review_id}")
            else:
                print(
                    "candidate_url_plan: "
                    f"company_key={company_key} decision={planned.decision} "
                    f"status={planned.review_status} selected_url={planned.selected_url or '<none>'} "
                    f"apply_allowed={planned.apply_allowed}"
                )
            items.append(planned)
        if args.apply:
            conn.commit()
        else:
            conn.rollback()

    payload = report_payload(benchmark_label=args.benchmark_label, items=items)
    json_path = args.output_json or output_dir / f"{args.benchmark_label}.json"
    md_path = args.output_markdown or output_dir / f"{args.benchmark_label}.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(markdown_report(payload), encoding="utf-8")
    print("json_report_written: " + str(json_path))
    print("markdown_report_written: " + str(md_path))
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CAND-001 reviewed candidate_url persistence from live bounded URL-Finder validation.")
    parser.add_argument("--benchmark-label", required=True)
    parser.add_argument("--company-key", action="append", required=True)
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--apply", action="store_true", help="Persist reviewed candidate_url changes. Default is dry-run.")
    parser.add_argument("--include-active-controlled", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=3.0)
    parser.add_argument("--max-url-candidates", type=int, default=4)
    parser.add_argument("--market-evidence-limit", type=int, default=20)
    parser.add_argument("--search-provider", action="append", default=["none"], choices=("none", "tavily"))
    parser.add_argument("--search-query-limit", type=int, default=4)
    parser.add_argument("--search-max-results", type=int, default=5)
    parser.add_argument("--search-timeout-seconds", type=float, default=8.0)
    parser.add_argument("--search-depth", choices=("basic", "advanced"), default="basic")
    parser.add_argument("--search-results-json", help="Optional offline search-result review context; not an apply source of truth.")
    parser.add_argument("--no-probe", action="store_true", help="Plan from generated URL candidates without HTTP probing; do not use for apply.")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.apply and args.no_probe:
        raise SystemExit("CAND-001 --apply requires HTTP probing; remove --no-probe.")
    run(args)


if __name__ == "__main__":
    main()
