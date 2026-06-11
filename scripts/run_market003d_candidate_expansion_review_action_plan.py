from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.market003d_candidate_expansion_review_action_plan import (
    build_action_plan,
    build_invalid_input_plan,
    build_missing_input_plan,
    load_source_report,
    write_outputs,
)

DEFAULT_INPUT = "exports/market003c_candidate_expansion_review/market003c_candidate_expansion_review.json"
DEFAULT_OUTPUT_DIR = "exports/market003d_candidate_expansion_review_action_plan"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MARKET-003D candidate expansion review action plan.")
    parser.add_argument("--input-json", default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    input_path = Path(args.input_json)
    generated_at = datetime.now(timezone.utc).isoformat()

    if not input_path.exists():
        report = build_missing_input_plan(input_path, generated_at=generated_at)
    else:
        try:
            source_report = load_source_report(input_path)
            report = build_action_plan(
                source_report,
                generated_at=generated_at,
                input_path=str(input_path),
            )
        except Exception as exc:  # noqa: BLE001 - CLI should produce bounded report instead of crashing.
            warning = f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else 'invalid input'}"
            report = build_invalid_input_plan(input_path, warning, generated_at=generated_at)

    outputs = write_outputs(report, Path(args.output_dir))
    print_summary(report, outputs)
    return 0


def print_summary(report: dict, outputs: dict[str, str]) -> None:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    print("# MARKET-003D Candidate Expansion Review Action Plan")
    print(f"input_status={report.get('input_status')}")
    if report.get("input_warning"):
        print(f"input_warning={report.get('input_warning')}")
    print(f"item_count={summary.get('item_count', 0)}")
    print(f"human_review_queue_count={summary.get('human_review_queue_count', 0)}")
    print("candidate_creation_count=0")
    print("gate_decision_count=0")
    print("connector_activation_count=0")
    for key, value in outputs.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    raise SystemExit(main())
