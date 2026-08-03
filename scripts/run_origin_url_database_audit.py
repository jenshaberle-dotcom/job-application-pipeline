"""Run the default origin finder read-only for current companies in the DB.

The audit imports the stable default entry point so every execution receives the
same symbol-brand identity, legal-suffix, follow-up-domain, and staging contract
as the operator CLI. Database inventory is completed and rolled back before any
external request is made.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from scripts.run_origin_source_discovery_agent import load_local_env_file
from scripts.run_origin_url_default_repair import run_default_repair_for_company
from src.config import get_database_config

DEFAULT_OUTPUT_DIR = Path.home() / "product_v1_runtime_artifacts"


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def load_current_companies(
    conn: psycopg.Connection[Any],
    *,
    statuses: tuple[str, ...],
    company_keys: tuple[str, ...],
    maximum: int | None,
) -> list[dict[str, object]]:
    where = ["company_key IS NOT NULL", "btrim(company_key) <> ''"]
    params: list[object] = []
    if statuses:
        where.append("status = ANY(%s)")
        params.append(list(statuses))
    if company_keys:
        where.append("company_key = ANY(%s)")
        params.append(list(company_keys))
    limit_sql = ""
    if maximum is not None:
        limit_sql = " LIMIT %s"
        params.append(maximum)
    sql = f"""
        SELECT DISTINCT ON (company_key)
               id, company_key, company_name, status, candidate_url, risk_level,
               updated_at
        FROM employer_origin_source_candidates
        WHERE {' AND '.join(where)}
        ORDER BY company_key, updated_at DESC NULLS LAST, id DESC
        {limit_sql}
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, tuple(params))
        return [dict(row) for row in cur.fetchall()]


def repair_args(args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        target_location=args.target_location,
        target_locale=args.target_locale,
        reviewed_by=args.reviewed_by,
        timeout_seconds=args.timeout_seconds,
        max_candidates=args.max_url_candidates,
        max_url_candidates=args.max_url_candidates,
        market_evidence_limit=args.market_evidence_limit,
        search_query_limit=args.search_query_limit,
        initial_search_query_limit=args.initial_search_query_limit,
        domain_followup_query_limit=args.domain_followup_query_limit,
        max_brand_host_hypotheses=args.max_brand_host_hypotheses,
        max_adaptive_candidates=args.max_adaptive_candidates,
        search_max_results=args.search_max_results,
        search_timeout_seconds=args.search_timeout_seconds,
        search_depth=args.search_depth,
        search_results_json=None,
        operator_url=[],
        max_evidence_candidates=args.max_evidence_candidates,
        max_evidence_http_requests=args.max_evidence_http_requests,
        evidence_timeout_seconds=args.evidence_timeout_seconds,
        max_response_bytes=args.max_response_bytes,
        llm_model=args.llm_model,
        llm_reasoning_effort=args.llm_reasoning_effort,
        llm_max_output_tokens=args.llm_max_output_tokens,
        llm_reserved_input_tokens=args.llm_reserved_input_tokens,
        llm_timeout_seconds=args.llm_timeout_seconds,
        max_estimated_llm_cost_usd_per_company=(
            args.max_estimated_llm_cost_usd_per_company
        ),
        search_llm_model=args.search_llm_model,
        search_llm_reasoning_effort=args.search_llm_reasoning_effort,
        search_llm_max_output_tokens=args.search_llm_max_output_tokens,
        search_llm_reserved_input_tokens=args.search_llm_reserved_input_tokens,
        search_llm_timeout_seconds=args.search_llm_timeout_seconds,
        max_search_llm_cost_usd_per_company=(
            args.max_search_llm_cost_usd_per_company
        ),
        disable_tavily=args.disable_tavily,
        disable_llm=args.disable_llm,
    )


def _request_attempted(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    direct = value.get("request_attempted")
    if isinstance(direct, bool):
        return direct
    for key in ("provider_result", "result", "observation"):
        nested = value.get(key)
        if _request_attempted(nested):
            return True
    return False


def request_accounting(payload: Mapping[str, object]) -> dict[str, int]:
    """Return external, web-search, and actual LLM request counts.

    Stage ``provider_request_count`` is an external-request total. The early LLM
    stage includes one OpenAI request plus any Tavily queries proposed by that
    model, so it must not be reused as an LLM count.
    """

    repair = payload.get("default_repair")
    stages = repair.get("stages") if isinstance(repair, Mapping) else None
    external_requests = 0
    if isinstance(stages, list):
        for stage in stages:
            if isinstance(stage, Mapping):
                external_requests += int(stage.get("provider_request_count") or 0)

    early_llm = int(_request_attempted(payload.get("early_llm_observation")))
    late_llm = int(_request_attempted(payload.get("llm_observation")))
    llm_requests = early_llm + late_llm
    web_search_requests = max(0, external_requests - llm_requests)
    return {
        "external_provider_requests": external_requests,
        "web_search_requests": web_search_requests,
        "llm_requests": llm_requests,
    }


def result_row(
    company: Mapping[str, object],
    payload: Mapping[str, object] | None,
    *,
    error: str | None = None,
    budget_blocked: bool = False,
) -> dict[str, object]:
    repair = payload.get("default_repair") if isinstance(payload, Mapping) else None
    repair_map = repair if isinstance(repair, Mapping) else {}
    accounting = (
        request_accounting(payload)
        if isinstance(payload, Mapping)
        else {
            "external_provider_requests": 0,
            "web_search_requests": 0,
            "llm_requests": 0,
        }
    )
    adaptive = payload.get("adaptive_search") if isinstance(payload, Mapping) else None
    adaptive_map = adaptive if isinstance(adaptive, Mapping) else {}
    selected_url = repair_map.get("selected_url")
    selected_host = ""
    if isinstance(selected_url, str) and selected_url:
        selected_host = str(urlparse(selected_url).hostname or "").lower()
    return {
        "candidate_id": company.get("id"),
        "company_key": company.get("company_key"),
        "company_name": company.get("company_name"),
        "candidate_status": company.get("status"),
        "candidate_url_before": company.get("candidate_url"),
        "risk_level": company.get("risk_level"),
        "final_state": (
            "not_run_budget_guard" if budget_blocked else repair_map.get("final_state")
        ),
        "selected_stage": repair_map.get("selected_stage"),
        "selected_url": selected_url,
        "selected_host": selected_host or None,
        "recommended_url": repair_map.get("recommended_url"),
        "operator_review_required": repair_map.get("operator_review_required"),
        "configuration_blocked": repair_map.get("configuration_blocked"),
        "repair_exhausted": repair_map.get("repair_exhausted"),
        "provider_requests": accounting["external_provider_requests"],
        "web_search_requests": accounting["web_search_requests"],
        "llm_requests": accounting["llm_requests"],
        "attempted_query_count": len(adaptive_map.get("attempted_queries", [])),
        "attempted_url_count": len(adaptive_map.get("attempted_urls", [])),
        "repeated_state_detected": adaptive_map.get("repeated_state_detected"),
        "error": error,
    }


def markdown_report(report: Mapping[str, object]) -> str:
    summary = report["summary"]
    rows = report["companies"]
    assert isinstance(summary, Mapping)
    assert isinstance(rows, list)
    lines = [
        "# Origin URL Database Audit",
        "",
        f"Generated: `{report['generated_at_utc']}`",
        "",
        "## Boundary",
        "",
        "Read-only database inventory followed by bounded external origin discovery. No candidate URL, connector, source, Bronze/Silver, ranking or scheduler state is written.",
        "",
        "## Summary",
        "",
        f"- Companies inventoried: {summary['company_count']}",
        f"- Companies executed: {summary['executed_count']}",
        f"- Selected: {summary['selected_count']}",
        f"- Operator review: {summary['operator_review_count']}",
        f"- Configuration blocked: {summary['configuration_blocked_count']}",
        f"- Repair exhausted: {summary['repair_exhausted_count']}",
        f"- Errors: {summary['error_count']}",
        f"- Budget-guarded/not run: {summary['budget_guard_count']}",
        f"- External provider requests: {summary['provider_request_count']}",
        f"- Web-search requests: {summary['web_search_request_count']}",
        f"- LLM requests: {summary['llm_request_count']}",
        "",
        "## Company Results",
        "",
        "| Company | Final state | Stage | Selected URL | External | Search | LLM | Repeat | Error |",
        "|---|---|---|---|---:|---:|---:|---|---|",
    ]
    for row in rows:
        assert isinstance(row, Mapping)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("company_key") or ""),
                    str(row.get("final_state") or ""),
                    str(row.get("selected_stage") or ""),
                    str(row.get("selected_url") or "<none>"),
                    str(row.get("provider_requests") or 0),
                    str(row.get("web_search_requests") or 0),
                    str(row.get("llm_requests") or 0),
                    str(row.get("repeated_state_detected")),
                    str(row.get("error") or ""),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(
    report: Mapping[str, object],
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    json_path = output_dir / f"origin_url_database_audit_{stamp}.json"
    md_path = output_dir / f"origin_url_database_audit_{stamp}.md"
    csv_path = output_dir / f"origin_url_database_audit_{stamp}.csv"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(markdown_report(report), encoding="utf-8")
    rows = report["companies"]
    assert isinstance(rows, list)
    fieldnames = list(rows[0].keys()) if rows else ["company_key", "final_state"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)  # type: ignore[arg-type]
    return json_path, md_path, csv_path


def run(args: argparse.Namespace) -> dict[str, object]:
    maximum = args.max_companies if args.max_companies > 0 else None
    with connect() as conn:
        companies = load_current_companies(
            conn,
            statuses=tuple(args.status),
            company_keys=tuple(args.company_key),
            maximum=maximum,
        )
        conn.rollback()

    repair = repair_args(args)
    rows: list[dict[str, object]] = []
    full_payloads: list[dict[str, object]] = []
    provider_total = 0
    web_search_total = 0
    llm_total = 0

    for index, company in enumerate(companies, start=1):
        key = str(company.get("company_key") or "")
        if (
            provider_total >= args.max_provider_requests
            or llm_total >= args.max_llm_requests
        ):
            row = result_row(company, None, budget_blocked=True)
            rows.append(row)
            print(
                f"origin_db_audit: {index}/{len(companies)} company_key={key} "
                "final_state=not_run_budget_guard"
            )
            continue
        try:
            payload = run_default_repair_for_company(repair, key)
        except Exception as exc:  # noqa: BLE001 - per-company audit isolation
            message = f"{type(exc).__name__}: {' '.join(str(exc).split())[:500]}"
            rows.append(result_row(company, None, error=message))
            print(
                f"origin_db_audit: {index}/{len(companies)} company_key={key} "
                f"final_state=error error={message}"
            )
            if args.stop_on_error:
                raise
            continue
        row = result_row(company, payload)
        provider_total += int(row["provider_requests"])
        web_search_total += int(row["web_search_requests"])
        llm_total += int(row["llm_requests"])
        rows.append(row)
        full_payloads.append(payload)
        print(
            f"origin_db_audit: {index}/{len(companies)} company_key={key} "
            f"final_state={row['final_state']} selected_stage={row['selected_stage']} "
            f"selected_url={row['selected_url'] or '<none>'} "
            f"provider_requests={row['provider_requests']} "
            f"web_search_requests={row['web_search_requests']} "
            f"llm_requests={row['llm_requests']}"
        )

    final_counts = Counter(str(row.get("final_state") or "error") for row in rows)
    selected_count = sum(
        1 for row in rows if str(row.get("final_state") or "").startswith("selected_")
    )
    report: dict[str, object] = {
        "schema_version": "origin_url_database_audit.v2",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "review_output_only_not_pipeline_input": True,
        "database_write": False,
        "all_companies_requested": args.all_companies,
        "filters": {
            "statuses": list(args.status),
            "company_keys": list(args.company_key),
            "max_companies": maximum,
        },
        "request_accounting": {
            "provider_requests": "all external Tavily and OpenAI requests",
            "web_search_requests": "Tavily requests only",
            "llm_requests": "actual OpenAI requests only",
        },
        "budget": {
            "max_provider_requests": args.max_provider_requests,
            "max_llm_requests": args.max_llm_requests,
            "provider_requests_used": provider_total,
            "web_search_requests_used": web_search_total,
            "llm_requests_used": llm_total,
        },
        "summary": {
            "company_count": len(companies),
            "executed_count": len(full_payloads),
            "selected_count": selected_count,
            "operator_review_count": final_counts.get("operator_review_required", 0),
            "configuration_blocked_count": final_counts.get(
                "repair_configuration_blocked", 0
            ),
            "repair_exhausted_count": final_counts.get("repair_exhausted", 0),
            "error_count": sum(1 for row in rows if row.get("error")),
            "budget_guard_count": final_counts.get("not_run_budget_guard", 0),
            "provider_request_count": provider_total,
            "web_search_request_count": web_search_total,
            "llm_request_count": llm_total,
            "final_state_counts": dict(sorted(final_counts.items())),
            "selected_stage_counts": dict(
                sorted(
                    Counter(
                        str(row.get("selected_stage"))
                        for row in rows
                        if row.get("selected_stage")
                    ).items()
                )
            ),
        },
        "companies": rows,
        "repair_payloads": full_payloads,
    }
    json_path, md_path, csv_path = write_outputs(report, args.output_dir)
    print(f"artifact_json: {json_path}")
    print(f"artifact_markdown: {md_path}")
    print(f"artifact_csv: {csv_path}")
    print("RESULT: ORIGIN_URL_DATABASE_AUDIT_COMPLETED")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run default origin repair read-only for current DB companies."
    )
    parser.add_argument(
        "--all-companies",
        action="store_true",
        required=True,
        help="Explicit acknowledgement that the selected inventory should run.",
    )
    parser.add_argument("--company-key", action="append", default=[])
    parser.add_argument("--status", action="append", default=[])
    parser.add_argument("--max-companies", type=int, default=0)
    parser.add_argument("--max-provider-requests", type=int, default=250)
    parser.add_argument("--max-llm-requests", type=int, default=50)
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--target-locale", default="de")
    parser.add_argument("--reviewed-by", default="database_audit")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--max-url-candidates", type=int, default=12)
    parser.add_argument("--market-evidence-limit", type=int, default=30)
    parser.add_argument("--search-query-limit", type=int, default=5)
    parser.add_argument("--initial-search-query-limit", type=int, default=5)
    parser.add_argument("--domain-followup-query-limit", type=int, default=3)
    parser.add_argument("--max-brand-host-hypotheses", type=int, default=6)
    parser.add_argument("--max-adaptive-candidates", type=int, default=18)
    parser.add_argument("--search-max-results", type=int, default=5)
    parser.add_argument("--search-timeout-seconds", type=float, default=8.0)
    parser.add_argument(
        "--search-depth", choices=("basic", "advanced"), default="advanced"
    )
    parser.add_argument("--max-evidence-candidates", type=int, default=4)
    parser.add_argument("--max-evidence-http-requests", type=int, default=12)
    parser.add_argument("--evidence-timeout-seconds", type=float, default=8.0)
    parser.add_argument("--max-response-bytes", type=int, default=750_000)
    parser.add_argument(
        "--llm-model",
        default=os.getenv("ORIGIN_ADJUDICATION_MODEL", "gpt-5.4-mini"),
    )
    parser.add_argument("--llm-reasoning-effort", default="low")
    parser.add_argument("--llm-max-output-tokens", type=int, default=600)
    parser.add_argument("--llm-reserved-input-tokens", type=int, default=5000)
    parser.add_argument("--llm-timeout-seconds", type=float, default=60.0)
    parser.add_argument(
        "--max-estimated-llm-cost-usd-per-company", type=float, default=0.01
    )
    parser.add_argument(
        "--search-llm-model",
        default=os.getenv("ORIGIN_SEARCH_HYPOTHESIS_MODEL", "gpt-5.4-mini"),
    )
    parser.add_argument("--search-llm-reasoning-effort", default="low")
    parser.add_argument("--search-llm-max-output-tokens", type=int, default=500)
    parser.add_argument("--search-llm-reserved-input-tokens", type=int, default=3500)
    parser.add_argument("--search-llm-timeout-seconds", type=float, default=60.0)
    parser.add_argument(
        "--max-search-llm-cost-usd-per-company", type=float, default=0.01
    )
    parser.add_argument("--disable-tavily", action="store_true")
    parser.add_argument("--disable-llm", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> None:
    load_local_env_file()
    args = build_parser().parse_args()
    if args.max_companies < 0:
        raise SystemExit("--max-companies must not be negative")
    if args.max_provider_requests < 0 or args.max_llm_requests < 0:
        raise SystemExit("request ceilings must not be negative")
    run(args)


if __name__ == "__main__":
    main()
