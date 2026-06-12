from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.expand007_controlled_candidate_creation_apply_gate_readiness import (  # noqa: E402
    build_apply_gate_readiness_report,
    find_latest_expand004_report,
    find_latest_expand006_report,
    load_expand004_report,
    load_expand006_report,
    write_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EXPAND-007 controlled candidate creation apply-gate readiness review.")
    parser.add_argument(
        "--expand004-input",
        type=Path,
        default=None,
        help="EXPAND-004 dry-run manifest JSON. Defaults to latest exports/expand004... report.",
    )
    parser.add_argument(
        "--expand006-input",
        type=Path,
        default=None,
        help="EXPAND-006 evidence review JSON. Defaults to latest exports/expand006... report.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/expand007_controlled_candidate_creation_apply_gate_readiness"),
        help="Output directory for JSON/Markdown/CSV artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expand004_path = args.expand004_input or find_latest_expand004_report()
    if expand004_path is None:
        print("input_status=input_missing")
        print("input_warning=No EXPAND-004 report found under exports/expand004_controlled_candidate_creation_dry_run*")
        return 2

    expand006_path = args.expand006_input or find_latest_expand006_report()
    if expand006_path is None:
        print("input_status=input_missing")
        print("input_warning=No EXPAND-006 report found under exports/expand006_candidate_creation_evidence_review*")
        return 2

    report = build_apply_gate_readiness_report(
        load_expand004_report(expand004_path),
        load_expand006_report(expand006_path),
        expand004_path=str(expand004_path),
        expand006_path=str(expand006_path),
    )
    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})
    boundary = report.get("apply_gate_boundary", {})

    print("# EXPAND-007 Controlled Candidate Creation Apply-Gate Readiness")
    print("input_status=ok")
    print(f"expand004_input={expand004_path}")
    print(f"expand006_input={expand006_path}")
    print(f"overall_status={report.get('overall_status')}")
    for key in [
        "candidate_assessment_count",
        "selected_candidate_creation_dry_run_count",
        "ready_for_manual_apply_gate_design_count",
        "generic_gap_ids",
        "expand004_overall_status",
        "expand006_database_status",
        "expand006_review_signal_strength",
    ]:
        print(f"{key}={summary.get(key)}")
    print(f"apply_gate_design_allowed={boundary.get('apply_gate_design_allowed_by_this_report')}")
    print(f"candidate_creation_execution_allowed={boundary.get('candidate_creation_execution_allowed_by_this_report')}")
    print(f"next_action={report.get('next_action')}")
    print(f"json={outputs['json']}")
    print(f"csv={outputs['csv']}")
    print(f"markdown={outputs['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
