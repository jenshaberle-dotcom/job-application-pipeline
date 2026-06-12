from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.generic002_benchmark_gap_closure_plan import (  # noqa: E402
    build_benchmark_gap_closure_plan,
    find_latest_generic001_report,
    load_generic001_report,
    write_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan GENERIC-001 benchmark gap closure without mutating pipeline state.")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="GENERIC-001 proof gate JSON. Defaults to latest exports/generic001... report.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/generic002_benchmark_gap_closure_plan"),
        help="Output directory for JSON/Markdown review artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input or find_latest_generic001_report()
    if input_path is None:
        print("input_status=input_missing")
        print("input_warning=No GENERIC-001 report found under exports/generic001_pipeline_generics_proof_gate*")
        print("next_action=run python scripts/run_generic001_pipeline_generics_proof_gate.py first")
        return 2

    generic001_report = load_generic001_report(input_path)
    report = build_benchmark_gap_closure_plan(generic001_report, input_path=str(input_path))
    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})

    print("# GENERIC-002 Benchmark Gap Closure Plan")
    print("input_status=ok")
    print(f"input={input_path}")
    print(f"overall_status={report.get('overall_status')}")
    for key in ["gap_count", "ready_to_close_gap_count", "blocked_gap_count", "ready_to_close_gaps", "blocked_gaps"]:
        print(f"{key}={summary.get(key)}")
    if report.get("rerun_command"):
        print(f"rerun_command={report.get('rerun_command')}")
    print(f"next_action={report.get('next_action')}")
    print(f"json={outputs['json']}")
    print(f"markdown={outputs['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
