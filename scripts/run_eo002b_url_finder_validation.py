"""Run EO-002B read-only URL Finder validation for a controlled guest list.

This script is intentionally report-only. It reads employer-origin candidates,
runs the existing Origin Source Discovery agent for each selected company and
writes/prints a compact validation report. It preserves the EO-002B boundary
terms ``no_candidate_url_write``, ``no_connector_registration``,
``no_source_activation``, ``no_bronze_silver_write`` and
``no_scheduler_change`` through the report payload. It does not reset
candidates; use ``scripts.run_employer_origin_reprocess_benchmark`` for the
separate dry-run first reset/next-safe-action workflow.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.run_employer_origin_reprocess_benchmark import (
    connect,
    load_candidate_keys,
    normalize_company_keys,
)
from scripts.run_origin_source_discovery_agent import load_local_env_file, run_for_company
from src.search_intelligence.eo002b_url_finder_validation import (
    UrlFinderValidationMetric,
    metric_from_discovery_payload,
    report_payload,
)

DEFAULT_EXPORT_DIR = Path("exports/eo002b_candidate_reprocessing_url_finder_validation")


def load_company_keys(args: argparse.Namespace) -> list[str]:
    explicit = normalize_company_keys(args.company_key)
    if explicit:
        return explicit
    with connect() as conn:
        candidates = load_candidate_keys(
            conn,
            include_active_controlled=args.include_active_controlled,
            limit=args.max_candidates,
        )
    return [company_key for _, company_key, _ in candidates]


def build_origin_discovery_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
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


def run_validation(args: argparse.Namespace) -> dict[str, object]:
    company_keys = load_company_keys(args)
    if args.company_key:
        requested = normalize_company_keys(args.company_key)
        missing = [company_key for company_key in requested if company_key not in company_keys]
        if missing:
            print(
                "guest_list_missing_or_protected: "
                + ", ".join(missing)
                + " (not found, over limit, or active_controlled without --include-active-controlled)"
            )

    origin_args = build_origin_discovery_args(args)
    metrics: list[UrlFinderValidationMetric] = []
    raw_results: list[dict[str, object]] = []
    for company_key in company_keys[: args.max_candidates]:
        payload = run_for_company(origin_args, company_key)
        raw_results.append(payload)
        metric = metric_from_discovery_payload(payload, gate_stop=None)
        metrics.append(metric)
        print(
            "url_finder_metric: "
            f"company_key={metric.company_key} "
            f"tier={metric.success_tier} "
            f"decision={metric.decision} "
            f"confidence={metric.confidence_score:.3f} "
            f"selected_url={metric.selected_url or '<none>'} "
            f"alternatives={metric.alternative_url_count} "
            f"rejected={metric.rejected_url_count} "
            f"false_negative_candidate={metric.false_negative_candidate}"
        )

    report = report_payload(metrics, benchmark_label=args.benchmark_label)
    report["raw_origin_discovery_results"] = raw_results if args.include_raw_results else []
    return report


def write_report(report: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(f"report_written: {output_path}")


def default_output_path(benchmark_label: str) -> Path:
    safe_label = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in benchmark_label).strip("_")
    return DEFAULT_EXPORT_DIR / f"{safe_label or 'eo002b_url_finder_validation'}.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EO-002B read-only URL Finder validation for controlled candidate reprocessing.")
    parser.add_argument("--benchmark-label", required=True)
    parser.add_argument("--company-key", action="append", help="Explicit guest-list company key. Repeat for multiple candidates.")
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--include-active-controlled", action="store_true")
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--timeout-seconds", type=float, default=6.0)
    parser.add_argument("--max-url-candidates", type=int, default=30)
    parser.add_argument("--market-evidence-limit", type=int, default=20)
    parser.add_argument("--search-provider", action="append", default=["none"], choices=("none", "tavily"))
    parser.add_argument("--search-query-limit", type=int, default=4)
    parser.add_argument("--search-max-results", type=int, default=5)
    parser.add_argument("--search-timeout-seconds", type=float, default=8.0)
    parser.add_argument("--search-depth", default="basic", choices=("basic", "advanced"))
    parser.add_argument("--search-results-json", help="Optional offline search-result JSON replay file. Human-readable export only; not a pipeline input.")
    parser.add_argument("--no-probe", action="store_true", help="Score generated/evidence/search URLs without HTTP probing.")
    parser.add_argument("--include-raw-results", action="store_true", help="Embed full Origin Source Discovery payloads in the report for review.")
    parser.add_argument("--output", type=Path, help="Optional JSON report path. Defaults to exports/eo002b_candidate_reprocessing_url_finder_validation/<label>.json")
    return parser


def main() -> None:
    load_local_env_file()
    args = build_parser().parse_args()
    if len(args.search_provider) > 1 and "none" in args.search_provider:
        args.search_provider = [provider for provider in args.search_provider if provider != "none"]
    report = run_validation(args)
    print("summary: " + json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    write_report(report, args.output or default_output_path(args.benchmark_label))


if __name__ == "__main__":
    main()
