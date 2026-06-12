from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.expand004_controlled_candidate_creation_dry_run import (  # noqa: E402
    build_candidate_creation_dry_run_report,
    find_latest_expand003_report,
    find_latest_generic005_report,
    load_expand003_report,
    load_generic005_report,
    write_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EXPAND-004 controlled candidate creation dry-run manifest.")
    parser.add_argument(
        "--generic005-input",
        type=Path,
        default=None,
        help="GENERIC-005 final rerun JSON. Defaults to latest exports/generic005... report.",
    )
    parser.add_argument(
        "--expand003-input",
        type=Path,
        default=None,
        help="EXPAND-003 candidate review delta JSON. Defaults to latest exports/expand003... report.",
    )
    parser.add_argument(
        "--max-dry-run-candidates",
        type=int,
        default=5,
        help="Maximum selected preview-only candidate creation dry-run items.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/expand004_controlled_candidate_creation_dry_run"),
        help="Output directory for JSON/Markdown/CSV artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generic005_path = args.generic005_input or find_latest_generic005_report()
    if generic005_path is None:
        print("input_status=input_missing")
        print("input_warning=No GENERIC-005 report found under exports/generic005_stop_control_final_rerun*")
        return 2

    expand003_path = args.expand003_input or find_latest_expand003_report()
    if expand003_path is None:
        print("input_status=input_missing")
        print("input_warning=No EXPAND-003 report found under exports/expand003_candidate_review_delta_report*")
        return 2

    report = build_candidate_creation_dry_run_report(
        load_generic005_report(generic005_path),
        load_expand003_report(expand003_path),
        generic005_path=str(generic005_path),
        expand003_path=str(expand003_path),
        max_dry_run_candidates=args.max_dry_run_candidates,
    )
    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})

    print("# EXPAND-004 Controlled Candidate Creation Dry-Run")
    print("input_status=ok")
    print(f"generic005_input={generic005_path}")
    print(f"expand003_input={expand003_path}")
    print(f"overall_status={report.get('overall_status')}")
    for key in [
        "generics_ready_for_candidate_creation_dry_run",
        "generic005_overall_status",
        "generic001_final_overall_status",
        "generic001_final_gap_ids",
        "dry_run_item_count",
        "selected_candidate_creation_dry_run_count",
        "selected_candidate_creation_dry_run_keys",
        "blocked_by_generics_count",
        "stop_only_item_count",
    ]:
        print(f"{key}={summary.get(key)}")
    print(f"next_action={report.get('next_action')}")
    print(f"json={outputs['json']}")
    print(f"csv={outputs['csv']}")
    print(f"markdown={outputs['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
