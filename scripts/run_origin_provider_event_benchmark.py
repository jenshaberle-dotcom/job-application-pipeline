"""Run the bounded Tavily origin benchmark after an authenticated event trigger.

The private runtime reads and fingerprints the complete bounded PostgreSQL
projection once. All provider calls and HTTP probes then run from that immutable
in-memory snapshot, so a later local sleep or Tailscale interruption cannot abort
an already-authorized benchmark. Candidate-level checkpoints preserve completed
work across retried GitHub jobs.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from scripts.origin_provider_snapshot_runner import run_for_projection_row
from scripts.run_origin_source_discovery_agent import (
    _is_missing_or_placeholder_secret,
    load_local_env_file,
)
from src.config import get_database_config
from src.search_intelligence.origin_provider_event_runtime import (
    ProviderBudget,
    RUNTIME_BOUNDARY,
    load_origin_benchmark_projection,
    normalize_company_keys,
    projection_fingerprint,
)

CHECKPOINT_SCHEMA_VERSION = "origin_provider_event_checkpoint.v1"
REPORT_SCHEMA_VERSION = "origin_provider_event_benchmark.v2"


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
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_report(path: Path, report: dict[str, object]) -> None:
    write_json_atomic(path, report)


def _checkpoint_payload(
    *,
    fingerprint: str,
    company_keys: Sequence[str],
    results: Sequence[Mapping[str, object]],
    provider_request_attempts: int,
    complete: bool,
) -> dict[str, object]:
    return {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "review_output_only_not_pipeline_input": True,
        "projection_fingerprint": fingerprint,
        "company_keys": list(company_keys),
        "completed_company_keys": [str(item.get("company_key") or "") for item in results],
        "provider_request_attempts": provider_request_attempts,
        "complete": complete,
        "results": list(results),
    }


def write_checkpoint(
    path: Path | None,
    *,
    fingerprint: str,
    company_keys: Sequence[str],
    results: Sequence[Mapping[str, object]],
    provider_request_attempts: int,
    complete: bool,
) -> None:
    if path is None:
        return
    write_json_atomic(
        path,
        _checkpoint_payload(
            fingerprint=fingerprint,
            company_keys=company_keys,
            results=results,
            provider_request_attempts=provider_request_attempts,
            complete=complete,
        ),
    )


def load_checkpoint(
    path: Path | None,
    *,
    expected_fingerprint: str,
    company_keys: Sequence[str],
) -> tuple[list[dict[str, object]], int]:
    if path is None or not path.exists():
        return [], 0

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("invalid origin benchmark checkpoint payload")
    if payload.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise SystemExit("unsupported origin benchmark checkpoint schema")
    if payload.get("projection_fingerprint") != expected_fingerprint:
        raise SystemExit("checkpoint fingerprint does not match the dispatched projection")
    if payload.get("company_keys") != list(company_keys):
        raise SystemExit("checkpoint company ordering does not match the dispatched projection")

    raw_results = payload.get("results")
    if not isinstance(raw_results, list) or not all(isinstance(item, dict) for item in raw_results):
        raise SystemExit("checkpoint results must be a list of objects")
    results = [dict(item) for item in raw_results]
    completed_keys = [str(item.get("company_key") or "") for item in results]
    if completed_keys != list(company_keys[: len(completed_keys)]):
        raise SystemExit("checkpoint results are not an ordered projection prefix")
    if len(completed_keys) != len(set(completed_keys)):
        raise SystemExit("checkpoint contains duplicate company results")

    attempts = int(payload.get("provider_request_attempts") or 0)
    if attempts < 0:
        raise SystemExit("checkpoint provider request attempts must not be negative")
    return results, attempts


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
    planned_provider_requests = len(company_keys) * budget.search_query_limit
    if planned_provider_requests > budget.max_provider_requests:
        raise SystemExit("Provider request budget invariant violated before execution")

    results, provider_request_attempts = load_checkpoint(
        args.checkpoint,
        expected_fingerprint=actual_fingerprint,
        company_keys=company_keys,
    )
    if provider_request_attempts > budget.max_provider_requests:
        raise SystemExit("checkpoint already exceeds the provider request budget")
    resumed_result_count = len(results)

    write_checkpoint(
        args.checkpoint,
        fingerprint=actual_fingerprint,
        company_keys=company_keys,
        results=results,
        provider_request_attempts=provider_request_attempts,
        complete=False,
    )

    origin_args = build_origin_args(args)
    for row in projection[len(results) :]:
        def observe_provider_attempt(_provider: str, _query: str) -> None:
            nonlocal provider_request_attempts
            if provider_request_attempts >= budget.max_provider_requests:
                raise SystemExit("Provider request budget exhausted during execution")
            provider_request_attempts += 1

        result = run_for_projection_row(
            origin_args,
            row,
            request_attempt_observer=observe_provider_attempt,
        )
        results.append(result)
        write_checkpoint(
            args.checkpoint,
            fingerprint=actual_fingerprint,
            company_keys=company_keys,
            results=results,
            provider_request_attempts=provider_request_attempts,
            complete=False,
        )

    decision_counts = Counter(str(item.get("decision") or "unknown") for item in results)
    selected_count = decision_counts.get("origin_url_candidate_selected", 0)
    manual_count = decision_counts.get("manual_review_required", 0)
    report: dict[str, object] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "review_output_only_not_pipeline_input": True,
        "boundary": list(RUNTIME_BOUNDARY),
        "projection": {
            "fingerprint": actual_fingerprint,
            "candidate_count": len(projection),
            "company_keys": company_keys,
            "market_evidence_limit": args.market_evidence_limit,
            "database_reads_after_snapshot": 0,
        },
        "provider": {
            "name": "tavily",
            "search_depth": args.search_depth,
            "request_budget": budget.to_json(),
            "planned_provider_requests": planned_provider_requests,
            "provider_request_attempts": provider_request_attempts,
        },
        "recovery": {
            "checkpoint_enabled": args.checkpoint is not None,
            "resumed_result_count": resumed_result_count,
            "candidate_level_checkpoint": True,
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
    write_checkpoint(
        args.checkpoint,
        fingerprint=actual_fingerprint,
        company_keys=company_keys,
        results=results,
        provider_request_attempts=provider_request_attempts,
        complete=True,
    )
    print(
        "origin_provider_event_benchmark_complete: "
        f"candidates={len(results)} "
        f"provider_request_attempts={provider_request_attempts} "
        f"resumed_results={resumed_result_count} "
        f"selected={selected_count} "
        f"manual_review={manual_count} "
        f"output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
