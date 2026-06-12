from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.generic005_stop_control_final_rerun import (  # noqa: E402
    build_stop_control_final_rerun_report,
    find_latest_capture_csv,
    find_latest_expand003_report,
    find_latest_generic003_report,
    find_latest_generic004_report,
    load_expand003_report,
    load_generic003_report,
    load_generic004_report,
    read_capture_csv,
    write_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GENERIC-005 stop-control evidence final rerun review.")
    parser.add_argument(
        "--generic003-input",
        type=Path,
        default=None,
        help="GENERIC-003 benchmark control rerun JSON. Defaults to latest exports/generic003... report.",
    )
    parser.add_argument(
        "--generic004-input",
        type=Path,
        default=None,
        help="GENERIC-004 stop-control capture plan JSON. Defaults to latest exports/generic004... report.",
    )
    parser.add_argument(
        "--expand003-input",
        type=Path,
        default=None,
        help="EXPAND-003 candidate review delta JSON. Defaults to latest exports/expand003... report.",
    )
    parser.add_argument(
        "--capture-input",
        type=Path,
        default=None,
        help="Filled GENERIC-004 stop-control capture CSV. Defaults to latest generic004 capture CSV if present.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/generic005_stop_control_final_rerun"),
        help="Output directory for JSON/Markdown and nested GENERIC-001 final rerun artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generic003_path = args.generic003_input or find_latest_generic003_report()
    if generic003_path is None:
        print("input_status=input_missing")
        print("input_warning=No GENERIC-003 report found under exports/generic003_benchmark_control_rerun_review*")
        return 2

    generic004_path = args.generic004_input or find_latest_generic004_report()
    if generic004_path is None:
        print("input_status=input_missing")
        print("input_warning=No GENERIC-004 report found under exports/generic004_stop_control_evidence_capture_plan*")
        return 2

    expand003_path = args.expand003_input or find_latest_expand003_report()
    if expand003_path is None:
        print("input_status=input_missing")
        print("input_warning=No EXPAND-003 report found under exports/expand003_candidate_review_delta_report*")
        return 2

    capture_path = args.capture_input or find_latest_capture_csv()
    capture_rows = read_capture_csv(capture_path) if capture_path else []
    report = build_stop_control_final_rerun_report(
        load_generic003_report(generic003_path),
        load_generic004_report(generic004_path),
        load_expand003_report(expand003_path),
        capture_rows,
        generic003_path=str(generic003_path),
        generic004_path=str(generic004_path),
        expand003_path=str(expand003_path),
        capture_path=str(capture_path) if capture_path else None,
    )
    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})

    print("# GENERIC-005 Stop-Control Evidence / GENERIC-001 Final Rerun")
    print("input_status=ok")
    print(f"generic003_input={generic003_path}")
    print(f"generic004_input={generic004_path}")
    print(f"expand003_input={expand003_path}")
    if capture_path:
        print(f"capture_input={capture_path}")
    print(f"overall_status={report.get('overall_status')}")
    for key in [
        "positive_control_keys",
        "negative_control_keys",
        "accepted_stop_control_count",
        "rejected_stop_control_count",
        "closed_stop_gap_ids",
        "final_gap_ids",
        "generic001_final_overall_status",
        "generic001_final_failed_check_count",
    ]:
        print(f"{key}={summary.get(key)}")
    print(f"next_action={report.get('next_action')}")
    print(f"json={outputs['json']}")
    print(f"markdown={outputs['markdown']}")
    print(f"generic001_final_json={outputs['generic001_final_json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
