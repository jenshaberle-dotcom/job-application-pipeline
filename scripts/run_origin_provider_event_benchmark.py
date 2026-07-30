"""Run the bounded Tavily origin benchmark after an authenticated event trigger.

The command is designed for a private GitHub runtime connected to the local
PostgreSQL host through Tailscale. It re-reads the same database projection used
by the local dispatcher and stops before any provider call when the fingerprint
changed in transit.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from scripts.run_origin_source_discovery_agent import (
    _is_missing_or_placeholder_secret,
    load_local_env_file,
    run_for_company,
)
from src.config import get_database_config
from src.search_intelligence.origin_provider_event_runtime import (
    ProviderBudget,
    RUNTIME_BOUNDARY,
    load_origin_benchmark_projection,
    normalize_company_keys,
    projection_fingerprint,
)


def build_origin_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        target_location=args.target_location,
        reviewed_by="github_origin_provider_event_runtime",
        timeout_seconds=args.timeout_seconds,
        max_candidates=args.max_url_candidates,
        market_evidence_limit=args.market_evidence_limit,
        search_provider=["tavily"],
        search_query_limit=args.search_query_limit,
        search_max_results=args.search_max_results,
        search_timeout_seconds=args.search_timeout_seconds,
        search_depth=args.search_depth,
        search_results_json=None,
        no_probe=args.no_probe,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the fingerprint-bound read-only origin provider benchmark."
    )
    parser.add_argument("--expected-fingerprint", required=True)
    parser.add_argument("--company-key", action="append")
    parser.add_argument("--max-candidates", type=int, default=6)
    parser.add_argument("--search-query-limit", type=int, default=2)
    parser.add_argument("--search-max-results", type=int, default=5)
    parser.add_argument("--max-provider-requests", type=int, default=12)
    parser.add_argument("--market-evidence-limit", type=int, default=10)
    parser.add_argument("--max-url-candidates", type=int, default=20)
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--timeout-seconds", type=float, default=6.0)
    parser.add_argument("--search-timeout-seconds", type=float, default=8.0)
    parser.add_argument("--search-depth", choices=("basic", "advanced"), default="basic")
    parser.add_argument("--no-probe", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    load_local_env_file()
    args = build_parser().parse_args()
    if _is_missing_or_placeholder_secret(os.getenv("TAVILY_API_KEY")):
        raise SystemExit("TAVILY_API_KEY is missing or still a placeholder")

    budget = ProviderBudget(
        max_candidates=args.max_candidates,
        search_query_limit=args.search_query_limit,
        search_max_results=args.search_max_results,
        max_provider_requests=args.max_provider_requests,
    ).validate()

    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        projection = load_origin_benchmark_projection(
            conn,
            limit=budget.effective_candidate_limit,
            market_evidence_limit=args.market_evidence_limit,
            company_keys=normalize_company_keys(args.company_key),
            include_active_controlled=False,
        )

    actual_fingerprint = projection_fingerprint(projection)
    if actual_fingerprint != args.expected_fingerprint:
        raise SystemExit(
            "stale_dispatch_fingerprint: database projection changed after dispatch; "
            "no provider call executed"
        )
    if not projection:
        raise SystemExit("No eligible origin candidates in the fingerprint-bound projection")

    company_keys = [str(row["company_key"]) for row in projection]
    provider_request_attempts = len(company_keys) * budget.search_query_limit
    if provider_request_attempts > budget.max_provider_requests:
        raise SystemExit("Provider request budget invariant violated before execution")

    origin_args = build_origin_args(args)
    results: list[dict[str, object]] = []
    for company_key in company_keys:
        results.append(run_for_company(origin_args, company_key))

    decision_counts = Counter(str(item.get("decision") or "unknown") for item in results)
    selected_count = decision_counts.get("origin_url_candidate_selected", 0)
    manual_count = decision_counts.get("manual_review_required", 0)
    report: dict[str, object] = {
        "schema_version": "origin_provider_event_benchmark.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "review_output_only_not_pipeline_input": True,
        "boundary": list(RUNTIME_BOUNDARY),
        "projection": {
            "fingerprint": actual_fingerprint,
            "candidate_count": len(projection),
            "company_keys": company_keys,
            "market_evidence_limit": args.market_evidence_limit,
        },
        "provider": {
            "name": "tavily",
            "search_depth": args.search_depth,
            "request_budget": budget.to_json(),
            "provider_request_attempts": provider_request_attempts,
        },
        "summary": {
            "result_count": len(results),
            "selected_count": selected_count,
            "manual_review_count": manual_count,
            "not_found_count": decision_counts.get("not_found", 0),
            "selected_rate": round(selected_count / len(results), 4),
            "decision_counts": dict(sorted(decision_counts.items())),
        },
        "results": results,
    }
    write_report(args.output, report)
    print(
        "origin_provider_event_benchmark_complete: "
        f"candidates={len(results)} "
        f"provider_request_attempts={provider_request_attempts} "
        f"selected={selected_count} "
        f"manual_review={manual_count} "
        f"output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
