from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.expand003_candidate_review_delta_report import (  # noqa: E402
    build_candidate_review_delta_report,
    find_latest_expand002_report,
    load_expand002_report,
    write_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build EXPAND-003 candidate review delta report from EXPAND-002 artifacts.")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="EXPAND-002 JSON report. Defaults to latest exports/expand002... report.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/expand003_candidate_review_delta_report"),
        help="Output directory for JSON/CSV/Markdown review artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input or find_latest_expand002_report()
    if input_path is None:
        print("input_status=input_missing")
        print("input_warning=No EXPAND-002 report found under exports/expand002_controlled_external_probe_trial_run*")
        return 2

    report = load_expand002_report(input_path)
    delta_report = build_candidate_review_delta_report(report, input_path=str(input_path))
    outputs = write_outputs(delta_report, args.export_dir)
    summary = delta_report.get("summary", {})

    print("# EXPAND-003 Candidate Review Delta Report")
    print("input_status=ok")
    print(f"input={input_path}")
    for key in [
        "candidate_count",
        "ready_for_human_evidence_review_count",
        "ready_for_detail_followup_review_count",
        "weak_external_hint_no_candidate_creation_count",
        "candidate_creation_count",
        "gate_decision_count",
        "connector_activation_count",
        "database_write_count",
    ]:
        print(f"{key}={summary.get(key, 0)}")
    print(f"json={outputs['json']}")
    print(f"csv={outputs['csv']}")
    print(f"markdown={outputs['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
