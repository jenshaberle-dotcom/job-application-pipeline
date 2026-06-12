from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.generic006_stop_control_capture_repair_packet import (  # noqa: E402
    build_stop_control_capture_repair_packet,
    find_latest_capture_csv,
    find_latest_generic004_report,
    find_latest_generic005_report,
    load_generic004_report,
    load_generic005_report,
    read_capture_csv,
    write_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GENERIC-006 stop-control capture repair packet.")
    parser.add_argument(
        "--generic004-input",
        type=Path,
        default=None,
        help="GENERIC-004 stop-control capture plan JSON. Defaults to latest exports/generic004... report.",
    )
    parser.add_argument(
        "--generic005-input",
        type=Path,
        default=None,
        help="GENERIC-005 final rerun JSON. Defaults to latest exports/generic005... report.",
    )
    parser.add_argument(
        "--capture-input",
        type=Path,
        default=None,
        help="GENERIC-004 capture CSV. Defaults to latest generic004 capture CSV if present.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/generic006_stop_control_capture_repair_packet"),
        help="Output directory for JSON/Markdown/CSV repair packet artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generic004_path = args.generic004_input or find_latest_generic004_report()
    if generic004_path is None:
        print("input_status=input_missing")
        print("input_warning=No GENERIC-004 report found under exports/generic004_stop_control_evidence_capture_plan*")
        return 2

    generic005_path = args.generic005_input or find_latest_generic005_report()
    if generic005_path is None:
        print("input_status=input_missing")
        print("input_warning=No GENERIC-005 report found under exports/generic005_stop_control_final_rerun*")
        return 2

    capture_path = args.capture_input or find_latest_capture_csv()
    capture_rows = read_capture_csv(capture_path) if capture_path else []
    report = build_stop_control_capture_repair_packet(
        load_generic004_report(generic004_path),
        load_generic005_report(generic005_path),
        capture_rows,
        generic004_path=str(generic004_path),
        generic005_path=str(generic005_path),
        capture_path=str(capture_path) if capture_path else None,
    )
    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})

    print("# GENERIC-006 Stop-Control Capture Repair Packet")
    print("input_status=ok")
    print(f"generic004_input={generic004_path}")
    print(f"generic005_input={generic005_path}")
    if capture_path:
        print(f"capture_input={capture_path}")
    print(f"overall_status={report.get('overall_status')}")
    for key in [
        "capture_row_count",
        "ready_for_generic005_rerun_count",
        "blocked_capture_row_count",
        "missing_or_invalid_field_counts",
        "generic005_final_gap_ids",
        "safe_rerun_command_available",
    ]:
        print(f"{key}={summary.get(key)}")
    print(f"next_action={report.get('next_action')}")
    print(f"json={outputs['json']}")
    print(f"csv={outputs['csv']}")
    print(f"markdown={outputs['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
