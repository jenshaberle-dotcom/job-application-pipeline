from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.generic_pipeline_proof_gate import (  # noqa: E402
    build_generic_pipeline_proof_report,
    find_latest_expand003_report,
    find_latest_sensor_report,
    load_expand003_report,
    load_optional_sensor_report,
    write_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GENERIC-001 pipeline generics proof gate from review artifacts.")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="EXPAND-003 candidate review delta JSON. Defaults to latest exports/expand003... report.",
    )
    parser.add_argument(
        "--sensor-input",
        type=Path,
        default=None,
        help="Optional SENSOR-001H/001E JSON context. Defaults to latest matching sensor report if available.",
    )
    parser.add_argument(
        "--positive-control-key",
        action="append",
        default=[],
        help="Explicit known-good benchmark control company_key. Repeatable.",
    )
    parser.add_argument(
        "--negative-control-key",
        action="append",
        default=[],
        help="Explicit known stopped/blocked benchmark control company_key. Repeatable.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/generic001_pipeline_generics_proof_gate"),
        help="Output directory for JSON/CSV/Markdown review artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input or find_latest_expand003_report()
    if input_path is None:
        print("input_status=input_missing")
        print("input_warning=No EXPAND-003 report found under exports/expand003_candidate_review_delta_report*")
        return 2

    sensor_path = args.sensor_input or find_latest_sensor_report()
    expand003_report = load_expand003_report(input_path)
    sensor_report = load_optional_sensor_report(sensor_path) if sensor_path else None
    report = build_generic_pipeline_proof_report(
        expand003_report,
        expand003_path=str(input_path),
        sensor_report=sensor_report,
        sensor_path=str(sensor_path) if sensor_path else None,
        positive_control_keys=args.positive_control_key,
        negative_control_keys=args.negative_control_key,
    )
    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})

    print("# GENERIC-001 Pipeline Generics Proof Gate")
    print("input_status=ok")
    print(f"input={input_path}")
    if sensor_path:
        print(f"sensor_input={sensor_path}")
    print(f"overall_status={report.get('overall_status')}")
    for key in ["candidate_count", "passed_check_count", "failed_check_count", "failed_checks"]:
        print(f"{key}={summary.get(key)}")
    print(f"json={outputs['json']}")
    print(f"csv={outputs['csv']}")
    print(f"markdown={outputs['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
