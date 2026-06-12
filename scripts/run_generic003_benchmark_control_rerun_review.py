from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.generic003_benchmark_control_rerun_review import (  # noqa: E402
    build_benchmark_control_rerun_review,
    find_latest_expand003_report,
    find_latest_generic002_report,
    load_expand003_report,
    load_generic002_report,
    write_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GENERIC-003 artifact-only benchmark control rerun review.")
    parser.add_argument(
        "--generic002-input",
        type=Path,
        default=None,
        help="GENERIC-002 benchmark gap closure plan JSON. Defaults to latest exports/generic002... report.",
    )
    parser.add_argument(
        "--expand003-input",
        type=Path,
        default=None,
        help="EXPAND-003 candidate review delta JSON. Defaults to latest exports/expand003... report.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/generic003_benchmark_control_rerun_review"),
        help="Output directory for JSON/Markdown review artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generic002_path = args.generic002_input or find_latest_generic002_report()
    if generic002_path is None:
        print("input_status=input_missing")
        print("input_warning=No GENERIC-002 report found under exports/generic002_benchmark_gap_closure_plan*")
        print("next_action=run python scripts/run_generic002_benchmark_gap_closure_plan.py first")
        return 2

    expand003_path = args.expand003_input or find_latest_expand003_report()
    if expand003_path is None:
        print("input_status=input_missing")
        print("input_warning=No EXPAND-003 report found under exports/expand003_candidate_review_delta_report*")
        print("next_action=run python scripts/run_generic001_pipeline_generics_proof_gate.py first")
        return 2

    generic002_report = load_generic002_report(generic002_path)
    expand003_report = load_expand003_report(expand003_path)
    report = build_benchmark_control_rerun_review(
        generic002_report,
        expand003_report,
        generic002_path=str(generic002_path),
        expand003_path=str(expand003_path),
    )
    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})

    print("# GENERIC-003 Benchmark Control Rerun Review")
    print("input_status=ok")
    print(f"generic002_input={generic002_path}")
    print(f"expand003_input={expand003_path}")
    print(f"overall_status={report.get('overall_status')}")
    for key in [
        "closed_gap_count",
        "still_blocked_gap_count",
        "closed_gap_ids",
        "still_blocked_gap_ids",
        "positive_control_keys",
        "negative_control_keys",
    ]:
        print(f"{key}={summary.get(key)}")
    if report.get("control_rerun_command"):
        print(f"control_rerun_command={report.get('control_rerun_command')}")
    print(f"next_action={report.get('next_action')}")
    print(f"json={outputs['json']}")
    print(f"markdown={outputs['markdown']}")
    print(f"generic001_after_json={outputs['generic001_after_json']}")
    print(f"generic001_after_markdown={outputs['generic001_after_markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
