from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.generic010_report_chain_refresh_runner import (  # noqa: E402
    build_dry_run_report,
    run_chain,
    write_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GENERIC-010 Market→EXPAND→GENERIC report-chain refresh runner.")
    parser.add_argument("--dry-run", action="store_true", help="Only print/write the planned chain; do not run scripts.")
    parser.add_argument("--keep-going", action="store_true", help="Continue after a failing step; default stops downstream execution.")
    parser.add_argument(
        "--include-external-probe",
        action="store_true",
        help="Include the bounded external probe step. Default excludes it to avoid accidental external requests.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/generic010_report_chain_refresh_runner"),
        help="Output directory for JSON/Markdown runner reports.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = (
        build_dry_run_report(include_external_probe=args.include_external_probe)
        if args.dry_run
        else run_chain(
            repo_root=ROOT,
            include_external_probe=args.include_external_probe,
            keep_going=args.keep_going,
        )
    )
    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})

    print("# GENERIC-010 Report Chain Refresh Runner")
    print(f"overall_status={report.get('overall_status')}")
    print(f"step_count={summary.get('step_count', report.get('step_count'))}")
    print(f"failure_count={summary.get('failure_count')}")
    print(f"skipped_count={summary.get('skipped_count')}")
    print(f"include_external_probe={args.include_external_probe}")
    print(f"next_action={report.get('next_action')}")
    print(f"json={outputs['json']}")
    print(f"markdown={outputs['markdown']}")
    return 1 if report.get("overall_status") == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
