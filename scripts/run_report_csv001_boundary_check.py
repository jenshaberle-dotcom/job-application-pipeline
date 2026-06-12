from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.report_csv001_boundary import (  # noqa: E402
    DEFAULT_SCAN_ROOTS,
    build_csv_boundary_report,
    write_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run REPORT-CSV-001 export boundary check.")
    parser.add_argument(
        "--scan-root",
        action="append",
        default=None,
        help="Root directory to scan. Can be provided multiple times. Defaults to scripts/src/tests/docs.",
    )
    parser.add_argument(
        "--strict-unmarked-exports",
        action="store_true",
        help="Fail when export CSV references are not explicitly marked review_output_only_not_pipeline_input.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/report_csv001_boundary_check"),
        help="Output directory for JSON/Markdown review reports.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_csv_boundary_report(
        repo_root=ROOT,
        scan_roots=args.scan_root or DEFAULT_SCAN_ROOTS,
        strict_unmarked_exports=args.strict_unmarked_exports,
    )
    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})

    print("# REPORT-CSV-001 Export Boundary Hardening")
    print(f"overall_status={report.get('overall_status')}")
    for key in [
        "csv_reference_count",
        "disallowed_export_csv_read_count",
        "unmarked_export_csv_reference_count",
    ]:
        print(f"{key}={summary.get(key)}")
    print(f"strict_unmarked_exports={report.get('strict_unmarked_exports')}")
    print(f"next_action={report.get('next_action')}")
    print(f"json={outputs['json']}")
    print(f"markdown={outputs['markdown']}")
    return 1 if report.get("failure_ids") else 0


if __name__ == "__main__":
    raise SystemExit(main())
