from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.generic004_stop_control_evidence_capture_plan import (  # noqa: E402
    build_stop_control_evidence_capture_plan,
    find_latest_expand003_report,
    find_latest_generic003_report,
    load_expand003_report,
    load_generic003_report,
    write_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GENERIC-004 artifact-only stop-control evidence capture plan.")
    parser.add_argument(
        "--generic003-input",
        type=Path,
        default=None,
        help="GENERIC-003 benchmark control rerun review JSON. Defaults to latest exports/generic003... report.",
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
        default=Path("exports/generic004_stop_control_evidence_capture_plan"),
        help="Output directory for JSON/Markdown review artifacts. No CSV/Excel/export input is generated.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generic003_path = args.generic003_input or find_latest_generic003_report()
    if generic003_path is None:
        print("input_status=input_missing")
        print("input_warning=No GENERIC-003 report found under exports/generic003_benchmark_control_rerun_review*")
        print("next_action=run python scripts/run_generic003_benchmark_control_rerun_review.py first")
        return 2

    expand003_path = args.expand003_input or find_latest_expand003_report()
    if expand003_path is None:
        print("input_status=input_missing")
        print("input_warning=No EXPAND-003 report found under exports/expand003_candidate_review_delta_report*")
        print("next_action=run python scripts/run_expand003_candidate_review_delta_report.py first")
        return 2

    report = build_stop_control_evidence_capture_plan(
        load_generic003_report(generic003_path),
        load_expand003_report(expand003_path),
        generic003_path=str(generic003_path),
        expand003_path=str(expand003_path),
    )
    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})

    print("# GENERIC-004 Stop-Control Evidence Capture Plan")
    print("input_status=ok")
    print(f"generic003_input={generic003_path}")
    print(f"expand003_input={expand003_path}")
    print(f"overall_status={report.get('overall_status')}")
    for key in [
        "remaining_gap_ids",
        "eligible_safe_stop_candidate_count",
        "weak_only_not_eligible_candidate_count",
        "capture_template_row_count",
        "safe_stop_candidate_keys",
    ]:
        print(f"{key}={summary.get(key)}")
    if report.get("follow_up_command_if_template_filled"):
        print(f"follow_up_command={report.get('follow_up_command_if_template_filled')}")
    print(f"next_action={report.get('next_action')}")
    print(f"json={outputs['json']}")
    print(f"markdown={outputs['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
