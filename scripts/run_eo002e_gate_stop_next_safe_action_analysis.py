from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.eo002e_gate_stop_next_safe_analysis import (
    ActionRunSnapshot,
    CandidateSnapshot,
    GateReviewSnapshot,
    analyze_candidate,
    load_url_finder_evidence,
    markdown_report,
    report_payload,
)

DEFAULT_OUTPUT_DIR = Path("exports/eo002e_gate_stop_next_safe_action_evidence_analysis")


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _db_object_exists(conn: psycopg.Connection[Any], object_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("select to_regclass(%s)", (object_name,))
        row = cur.fetchone()
    return bool(row and row["to_regclass"])


def load_candidates(conn: psycopg.Connection[Any], *, company_keys: list[str], max_candidates: int) -> list[CandidateSnapshot]:
    params: list[Any] = []
    where = "true"
    order = "c.updated_at DESC NULLS LAST, c.id DESC"
    if company_keys:
        where = "c.company_key = ANY(%s)"
        params.append(company_keys)
        order = "array_position(%s::text[], c.company_key), c.id DESC"
        params.append(company_keys)
    params.append(max_candidates)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT
                c.id,
                c.company_key,
                c.company_name,
                c.status,
                c.candidate_url,
                c.risk_level
            FROM employer_origin_source_candidates c
            WHERE {where}
            ORDER BY {order}
            LIMIT %s
            """,
            params,
        )
        rows = cur.fetchall()
    return [
        CandidateSnapshot(
            candidate_id=int(row["id"]),
            company_key=str(row["company_key"]),
            company_name=str(row["company_name"]),
            status=str(row["status"]),
            candidate_url=row["candidate_url"],
            risk_level=row["risk_level"],
        )
        for row in rows
    ]


def load_gate_reviews(conn: psycopg.Connection[Any], candidate_id: int) -> list[GateReviewSnapshot]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (gate_name)
                gate_name,
                gate_order,
                gate_status,
                decision,
                stop_reason,
                evidence,
                updated_at
            FROM employer_origin_candidate_gate_reviews
            WHERE candidate_id = %s
            ORDER BY gate_name, updated_at DESC NULLS LAST, id DESC
            """,
            (candidate_id,),
        )
        rows = cur.fetchall()
    return [
        GateReviewSnapshot(
            gate_name=str(row["gate_name"]),
            gate_order=row["gate_order"],
            gate_status=row["gate_status"],
            decision=row["decision"],
            stop_reason=row["stop_reason"],
            evidence=row["evidence"],
            updated_at=str(row["updated_at"]) if row["updated_at"] is not None else None,
        )
        for row in rows
    ]


def load_action_runs(conn: psycopg.Connection[Any], candidate: CandidateSnapshot, *, limit: int = 5) -> list[ActionRunSnapshot]:
    if not _db_object_exists(conn, "search_intelligence_action_runs"):
        return []
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                action_type,
                status,
                exit_code,
                error_summary,
                gate_review_created,
                gate_review_gate_name,
                gate_review_status,
                gate_review_decision,
                started_at
            FROM search_intelligence_action_runs
            WHERE candidate_id = %s OR company_key = %s
            ORDER BY started_at DESC NULLS LAST, id DESC
            LIMIT %s
            """,
            (candidate.candidate_id, candidate.company_key, limit),
        )
        rows = cur.fetchall()
    return [
        ActionRunSnapshot(
            action_type=str(row["action_type"]),
            status=str(row["status"]),
            exit_code=row["exit_code"],
            error_summary=row["error_summary"],
            gate_review_created=row["gate_review_created"],
            gate_review_gate_name=row["gate_review_gate_name"],
            gate_review_status=row["gate_review_status"],
            gate_review_decision=row["gate_review_decision"],
            started_at=str(row["started_at"]) if row["started_at"] is not None else None,
        )
        for row in rows
    ]


def run(args: argparse.Namespace) -> dict[str, Any]:
    url_reports = [Path(raw) for raw in args.url_finder_report]
    url_finder_evidence = load_url_finder_evidence(url_reports) if url_reports else {}
    with connect() as conn:
        candidates = load_candidates(conn, company_keys=args.company_key, max_candidates=args.max_candidates)
        analyses = []
        for candidate in candidates:
            gates = load_gate_reviews(conn, candidate.candidate_id)
            action_runs = load_action_runs(conn, candidate)
            analyses.append(
                analyze_candidate(
                    candidate,
                    gates,
                    url_finder=url_finder_evidence.get(candidate.company_key),
                    action_runs=action_runs,
                )
            )
    return report_payload(
        analyses,
        benchmark_label=args.benchmark_label,
        source_url_finder_reports=[str(path) for path in url_reports],
    )


def write_reports(payload: dict[str, Any], output_dir: Path, label: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{label}_gate_stop_next_safe_analysis.json"
    md_path = output_dir / f"{label}_gate_stop_next_safe_analysis.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(markdown_report(payload), encoding="utf-8")
    return json_path, md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EO-002E read-only gate-stop and next-safe-action evidence analysis.")
    parser.add_argument("--benchmark-label", required=True)
    parser.add_argument("--company-key", action="append", default=[], help="Explicit candidate company key. Repeat for multiple candidates.")
    parser.add_argument("--max-candidates", type=int, default=25)
    parser.add_argument("--url-finder-report", action="append", default=[], help="Optional EO-002B URL Finder validation JSON report to join selected_url evidence.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    payload = run(args)
    json_path, md_path = write_reports(payload, args.output_dir, args.benchmark_label)
    print("summary:", json.dumps(payload["summary"], sort_keys=True, ensure_ascii=False))
    print("json_report_written:", json_path)
    print("markdown_report_written:", md_path)


if __name__ == "__main__":
    main()
