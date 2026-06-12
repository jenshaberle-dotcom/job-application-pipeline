from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.expand002_controlled_external_probe_trial_run import (  # noqa: E402
    build_invalid_input_report,
    build_missing_input_report,
    build_trial_run_report,
    load_trial_plan,
    write_outputs,
)

DEFAULT_INPUT = Path(
    "exports/market003f_expand001_controlled_manual_candidate_pipeline_trial/"
    "market003f_expand001_controlled_manual_candidate_pipeline_trial_plan.json"
)
DEFAULT_EXPORT_DIR = Path("exports/expand002_controlled_external_probe_trial_run")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EXPAND-002 controlled external probe trial.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument(
        "--execute-external-probes",
        action="store_true",
        help="Actually execute external provider requests. Omit for dry-run/manifest validation.",
    )
    parser.add_argument("--provider", choices=("dry_run", "fake", "tavily"), default="dry_run")
    parser.add_argument("--max-candidates", type=int, default=200)
    parser.add_argument("--max-queries-per-candidate", type=int, default=2)
    parser.add_argument("--max-results-per-query", type=int, default=5)
    parser.add_argument("--max-total-requests", type=int, default=500)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.execute_external_probes and args.provider == "dry_run":
        raise SystemExit("Use --provider fake or --provider tavily when --execute-external-probes is set.")
    if args.provider == "tavily" and args.execute_external_probes and not os.getenv("TAVILY_API_KEY"):
        raise SystemExit("TAVILY_API_KEY must be set for --provider tavily.")

    if not args.input.exists():
        report = build_missing_input_report(args.input)
    else:
        try:
            plan = load_trial_plan(args.input)
        except Exception as exc:  # noqa: BLE001 - bounded CLI report is preferable to traceback.
            report = build_invalid_input_report(args.input, str(exc))
        else:
            report = build_trial_run_report(
                plan,
                execute_external_probes=args.execute_external_probes,
                provider=args.provider,
                max_candidates=args.max_candidates,
                max_queries_per_candidate=args.max_queries_per_candidate,
                max_results_per_query=args.max_results_per_query,
                max_total_requests=args.max_total_requests,
                input_path=str(args.input),
            )

    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})
    print("# EXPAND-002 Controlled External Probe Trial Run")
    print(f"input_status={report.get('input_status', 'ok')}")
    print(f"execute_external_probes={args.execute_external_probes}")
    print(f"provider={args.provider}")
    print(f"planned_probe_count={summary.get('planned_probe_count', 0)}")
    print(f"external_requests_executed_count={summary.get('external_requests_executed_count', 0)}")
    print(f"completed_probe_count={summary.get('completed_probe_count', 0)}")
    print(f"failed_probe_count={summary.get('failed_probe_count', 0)}")
    print(f"candidate_with_external_hint_count={summary.get('candidate_with_external_hint_count', 0)}")
    print(f"candidate_with_weak_external_hint_count={summary.get('candidate_with_weak_external_hint_count', 0)}")
    print(f"blocked_after_provider_auth_failure_count={summary.get('blocked_after_provider_auth_failure_count', 0)}")
    print(f"duplicate_candidate_count={summary.get('duplicate_candidate_count', 0)}")
    print(f"duplicate_probe_count={summary.get('duplicate_probe_count', 0)}")
    print("candidate_creation_count=0")
    print("gate_decision_count=0")
    print("connector_activation_count=0")
    print("database_write_count=0")
    print(f"json={outputs['json']}")
    print(f"csv={outputs['csv']}")
    print(f"markdown={outputs['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
