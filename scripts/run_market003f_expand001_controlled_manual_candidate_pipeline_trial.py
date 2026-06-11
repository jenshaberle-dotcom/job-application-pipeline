from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.market003f_expand001_controlled_manual_candidate_pipeline_trial import (
    build_invalid_input_report,
    build_missing_input_report,
    build_trial_report,
    load_source_report,
    write_outputs,
)

DEFAULT_INPUT = Path(
    "exports/market003e_candidate_expansion_review_ui_queue_readiness/"
    "market003e_candidate_expansion_review_ui_queue_readiness.json"
)
DEFAULT_EXPORT_DIR = Path("exports/market003f_expand001_controlled_manual_candidate_pipeline_trial")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build MARKET-003F / EXPAND-001 controlled manual candidate pipeline trial plan."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input.exists():
        report = build_missing_input_report(args.input)
    else:
        try:
            source_report = load_source_report(args.input)
        except Exception as exc:  # noqa: BLE001 - bounded CLI report is preferable to a traceback here.
            report = build_invalid_input_report(args.input, str(exc))
        else:
            report = build_trial_report(source_report, input_path=str(args.input))

    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})
    print("# MARKET-003F / EXPAND-001 Controlled Manual Candidate Pipeline Trial")
    print(f"input_status={report.get('input_status')}")
    print(f"candidate_count={summary.get('candidate_count', 0)}")
    print(f"eligible_for_explicit_external_probe_count={summary.get('eligible_for_explicit_external_probe_count', 0)}")
    print(f"blocked_or_not_ready_count={summary.get('blocked_or_not_ready_count', 0)}")
    print("candidate_creation_count=0")
    print("gate_decision_count=0")
    print("connector_activation_count=0")
    print("external_requests_executed_by_this_command=0")
    print(f"json={outputs['json']}")
    print(f"csv={outputs['csv']}")
    print(f"markdown={outputs['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
