"""Run EO-002B read-only URL Finder validation with default repair.

The default path is no longer a single deterministic pass. Every unresolved
candidate automatically runs the bounded sequence deterministic -> Tavily ->
deep evidence -> eligible LLM adjudication.

Boundary terms remain explicit: ``no_candidate_url_write``,
``no_connector_registration``, ``no_source_activation``,
``no_bronze_silver_write`` and ``no_scheduler_change``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from scripts.run_employer_origin_reprocess_benchmark import (
    connect,
    load_candidate_keys,
    normalize_company_keys,
)
from scripts.run_origin_source_discovery_agent import (
    load_local_env_file,
    run_for_company as run_atomic_origin_discovery,
)
from scripts.run_origin_url_default_repair import run_default_repair_for_company
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
        target_locale=args.target_locale,
        reviewed_by=args.reviewed_by,
        timeout_seconds=args.timeout_seconds,
        max_candidates=args.max_url_candidates,
        max_url_candidates=args.max_url_candidates,
        market_evidence_limit=args.market_evidence_limit,
        search_provider=args.search_provider,
        search_query_limit=args.search_query_limit,
        search_max_results=args.search_max_results,
        search_timeout_seconds=args.search_timeout_seconds,
        search_depth=args.search_depth,
        search_results_json=args.search_results_json,
        no_probe=args.no_probe,
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
        disable_tavily=args.disable_tavily,
        disable_llm=args.disable_llm,
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
        if args.single_pass_diagnostic:
            payload = run_atomic_origin_discovery(origin_args, company_key)
        else:
            payload = run_default_repair_for_company(origin_args, company_key)
        raw_results.append(payload)
        metric = metric_from_discovery_payload(payload, gate_stop=None)
        metrics.append(metric)
        repair = payload.get("default_repair")
        repair_state = (
            repair.get("final_state")
            if isinstance(repair, dict)
            else "single_pass_diagnostic"
        )
        print(
            "url_finder_metric: "
            f"company_key={metric.company_key} "
            f"tier={metric.success_tier} "
            f"decision={metric.decision} "
            f"confidence={metric.confidence_score:.3f} "
            f"selected_url={metric.selected_url or '<none>'} "
            f"alternatives={metric.alternative_url_count} "
            f"rejected={metric.rejected_url_count} "
            f"repair_state={repair_state} "
            f"false_negative_candidate={metric.false_negative_candidate}"
        )

    report = report_payload(metrics, benchmark_label=args.benchmark_label)
    report["default_repair_enabled"] = not args.single_pass_diagnostic
    report["raw_origin_discovery_results"] = (
        raw_results if args.include_raw_results else []
    )
    return report


def write_report(report: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(f"report_written: {output_path}")


def default_output_path(benchmark_label: str) -> Path:
    safe_label = "".join(
        ch if ch.isalnum() or ch in {"-", "_"} else "_"
        for ch in benchmark_label
    ).strip("_")
    return DEFAULT_EXPORT_DIR / f"{safe_label or 'eo002b_url_finder_validation'}.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "EO-002B read-only URL Finder validation with mandatory default repair."
        )
    )
    parser.add_argument("--benchmark-label", required=True)
    parser.add_argument(
        "--company-key",
        action="append",
        help="Explicit guest-list company key. Repeat for multiple candidates.",
    )
    parser.add_argument("--max-candidates", type=int, default=5)
    parser.add_argument("--include-active-controlled", action="store_true")
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--target-locale", default="de")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--timeout-seconds", type=float, default=6.0)
    parser.add_argument("--max-url-candidates", type=int, default=12)
    parser.add_argument("--market-evidence-limit", type=int, default=30)
    parser.add_argument(
        "--search-provider",
        action="append",
        default=["none"],
        choices=("none", "tavily"),
        help=(
            "Compatibility option for single-pass diagnostics. The default repair "
            "path always escalates to Tavily after deterministic not_found."
        ),
    )
    parser.add_argument("--search-query-limit", type=int, default=4)
    parser.add_argument("--search-max-results", type=int, default=5)
    parser.add_argument("--search-timeout-seconds", type=float, default=8.0)
    parser.add_argument(
        "--search-depth",
        default="advanced",
        choices=("basic", "advanced"),
    )
    parser.add_argument("--search-results-json")
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
        "--max-estimated-llm-cost-usd-per-company",
        type=float,
        default=0.01,
    )
    parser.add_argument(
        "--disable-tavily",
        action="store_true",
        help="Diagnostic override; default repair reports configuration blocked.",
    )
    parser.add_argument(
        "--disable-llm",
        action="store_true",
        help="Diagnostic override; eligible LLM repair reports configuration blocked.",
    )
    parser.add_argument(
        "--single-pass-diagnostic",
        action="store_true",
        help="Explicit legacy diagnostic path; never the product default.",
    )
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="Only valid with --single-pass-diagnostic.",
    )
    parser.add_argument(
        "--include-raw-results",
        action="store_true",
        help="Embed full repair payloads in the review report.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Optional JSON report path. Defaults to "
            "exports/eo002b_candidate_reprocessing_url_finder_validation/<label>.json"
        ),
    )
    return parser


def main() -> None:
    load_local_env_file()
    args = build_parser().parse_args()
    if not 1 <= args.max_candidates <= 5:
        raise SystemExit("--max-candidates must be between 1 and 5")
    if args.no_probe and not args.single_pass_diagnostic:
        raise SystemExit("--no-probe is only valid with --single-pass-diagnostic")
    if len(args.search_provider) > 1 and "none" in args.search_provider:
        args.search_provider = [
            provider for provider in args.search_provider if provider != "none"
        ]
    report = run_validation(args)
    print(
        "summary: "
        + json.dumps(report["summary"], ensure_ascii=False, sort_keys=True)
    )
    write_report(
        report,
        args.output or default_output_path(args.benchmark_label),
    )


if __name__ == "__main__":
    main()
