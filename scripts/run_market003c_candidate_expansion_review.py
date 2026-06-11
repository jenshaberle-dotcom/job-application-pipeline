from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.market003c_candidate_expansion_review import build_report, write_outputs

MARKET_EVIDENCE_TABLE = "market_evidence"
CANDIDATES_TABLE = "employer_origin_source_candidates"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MARKET-003C candidate expansion review without promotion.")
    parser.add_argument("--output-dir", default="exports/market003c_candidate_expansion_review")
    parser.add_argument("--input-json", help="Optional fixture/input payload with market_evidence and existing_candidates arrays.")
    parser.add_argument("--max-evidence-rows", type=int, default=200)
    parser.add_argument("--docker-container", default="job_pipeline_postgres")
    parser.add_argument("--docker-user", default="job_user")
    parser.add_argument("--docker-db", default="job_pipeline")
    args = parser.parse_args()

    generated_at = datetime.now(timezone.utc).isoformat()
    export_dir = Path(args.output_dir)

    if args.input_json:
        payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
        report = build_report(
            market_evidence_payloads=_ensure_list(payload.get("market_evidence")),
            existing_candidate_payloads=_ensure_list(payload.get("existing_candidates")),
            generated_at=generated_at,
            db_access_method="input_json",
        )
        outputs = write_outputs(report, export_dir)
        print_summary(report, outputs)
        return 0

    try:
        market_exists = table_exists(MARKET_EVIDENCE_TABLE, args)
        candidates_exists = table_exists(CANDIDATES_TABLE, args)
        if not market_exists:
            report = build_report(
                market_evidence_payloads=[],
                existing_candidate_payloads=[],
                generated_at=generated_at,
                db_access_method="docker_exec_psql",
                input_status="market_evidence_relation_missing",
                input_warning=f"Relation {MARKET_EVIDENCE_TABLE!r} is not present. No review items were generated.",
            )
        else:
            market_evidence = read_table_payloads(MARKET_EVIDENCE_TABLE, args.max_evidence_rows, args)
            existing_candidates = read_table_payloads(CANDIDATES_TABLE, 10000, args) if candidates_exists else []
            report = build_report(
                market_evidence_payloads=market_evidence,
                existing_candidate_payloads=existing_candidates,
                generated_at=generated_at,
                db_access_method="docker_exec_psql",
            )
    except Exception as exc:  # noqa: BLE001 - CLI should produce a bounded report instead of crashing.
        report = build_report(
            market_evidence_payloads=[],
            existing_candidate_payloads=[],
            generated_at=generated_at,
            db_access_method="docker_exec_psql",
            input_status="db_unavailable",
            input_warning=f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else 'database unavailable'}",
        )

    outputs = write_outputs(report, export_dir)
    print_summary(report, outputs)
    return 0


def _ensure_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def table_exists(table_name: str, args: argparse.Namespace) -> bool:
    sql = (
        "select exists("
        "select 1 from information_schema.tables "
        "where table_schema = 'public' and table_name = "
        f"{sql_literal(table_name)}"
        ") as relation_exists"
    )
    rows = run_docker_json_query(wrap_json_query(sql), args)
    return bool(rows and rows[0].get("relation_exists"))


def read_table_payloads(table_name: str, limit: int, args: argparse.Namespace) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 10000))
    sql = f"select to_jsonb(t) as payload from {quote_identifier(table_name)} t limit {safe_limit}"
    rows = run_docker_json_query(wrap_json_query(sql), args)
    payloads: list[dict[str, Any]] = []
    for row in rows:
        payload = row.get("payload")
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def run_docker_json_query(sql: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    command = [
        "docker",
        "exec",
        "-i",
        args.docker_container,
        "psql",
        "-U",
        args.docker_user,
        "-d",
        args.docker_db,
        "-t",
        "-A",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        sql,
    ]
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "docker psql query failed")

    payload = result.stdout.strip()
    if not payload:
        return []
    parsed = json.loads(payload)
    return parsed if isinstance(parsed, list) else []


def wrap_json_query(inner_sql: str) -> str:
    return f"select coalesce(json_agg(row_to_json(rows)), '[]'::json) from ({inner_sql}) rows;"


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def print_summary(report: Mapping[str, Any], outputs: Mapping[str, str]) -> None:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    print("# MARKET-003C Candidate Expansion Review")
    print(f"overall_status={report.get('overall_status')}")
    if report.get("input_warning"):
        print(f"input_warning={report.get('input_warning')}")
    print(f"item_count={summary.get('item_count', 0)}")
    print(f"manual_review_required_count={summary.get('manual_review_required_count', 0)}")
    print("candidate_creation_count=0")
    print("gate_decision_count=0")
    print("connector_activation_count=0")
    for key, value in outputs.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    raise SystemExit(main())
