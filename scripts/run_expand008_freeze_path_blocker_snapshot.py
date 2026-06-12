from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.expand008_freeze_path_blocker_snapshot import (  # noqa: E402
    build_freeze_path_blocker_snapshot,
    find_latest_expand007_report,
    find_latest_generic005_report,
    find_latest_generic006_report,
    load_expand007_report,
    load_generic005_report,
    load_generic006_report,
    write_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EXPAND-008 freeze-path blocker snapshot.")
    parser.add_argument(
        "--generic005-input",
        type=Path,
        default=None,
        help="GENERIC-005 final rerun JSON. Defaults to latest exports/generic005... report.",
    )
    parser.add_argument(
        "--generic006-input",
        type=Path,
        default=None,
        help="Optional GENERIC-006 repair packet JSON. Defaults to latest exports/generic006... report if present.",
    )
    parser.add_argument(
        "--expand007-input",
        type=Path,
        default=None,
        help="EXPAND-007 apply-gate readiness JSON. Defaults to latest exports/expand007... report.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/expand008_freeze_path_blocker_snapshot"),
        help="Output directory for JSON/Markdown snapshot artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generic005_path = args.generic005_input or find_latest_generic005_report()
    if generic005_path is None:
        print("input_status=input_missing")
        print("input_warning=No GENERIC-005 report found under exports/generic005_stop_control_final_rerun*")
        return 2

    expand007_path = args.expand007_input or find_latest_expand007_report()
    if expand007_path is None:
        print("input_status=input_missing")
        print("input_warning=No EXPAND-007 report found under exports/expand007_controlled_candidate_creation_apply_gate_readiness*")
        return 2

    generic006_path = args.generic006_input or find_latest_generic006_report()
    generic006_report = load_generic006_report(generic006_path) if generic006_path else None
    report = build_freeze_path_blocker_snapshot(
        load_generic005_report(generic005_path),
        load_expand007_report(expand007_path),
        generic006_report,
        generic005_path=str(generic005_path),
        expand007_path=str(expand007_path),
        generic006_path=str(generic006_path) if generic006_path else None,
    )
    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})

    print("# EXPAND-008 Freeze-Path Blocker Snapshot")
    print("input_status=ok")
    print(f"generic005_input={generic005_path}")
    if generic006_path:
        print(f"generic006_input={generic006_path}")
    print(f"expand007_input={expand007_path}")
    print(f"overall_status={report.get('overall_status')}")
    for key in [
        "block_z_progress_numerator",
        "block_z_progress_denominator",
        "blocked_gate_count",
        "first_blocking_gate_id",
        "generic005_overall_status",
        "generic006_overall_status",
        "expand007_overall_status",
        "candidate_creation_apply_allowed",
    ]:
        print(f"{key}={summary.get(key)}")
    print(f"next_action={report.get('next_action')}")
    print(f"json={outputs['json']}")
    print(f"markdown={outputs['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
