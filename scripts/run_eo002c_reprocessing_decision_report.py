"""Build an EO-002C read-only decision report from EO-002B JSON reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.search_intelligence.eo002c_reprocessing_decision_report import (
    build_decision_report,
    load_metrics_from_reports,
    render_markdown_report,
)

DEFAULT_INPUT_DIR = Path("exports/eo002b_candidate_reprocessing_url_finder_validation")
DEFAULT_OUTPUT_DIR = Path("exports/eo002c_reprocessing_metrics_decision_report")


def discover_report_paths(args: argparse.Namespace) -> list[Path]:
    paths = [Path(raw_path) for raw_path in args.report_json if str(raw_path).strip()]
    if args.input_dir:
        paths.extend(sorted(Path(args.input_dir).glob("*.json")))
    if not paths and DEFAULT_INPUT_DIR.exists():
        paths.extend(sorted(DEFAULT_INPUT_DIR.glob("*.json")))
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        normalized = path.resolve()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(path)
    return unique


def write_outputs(report: dict[str, object], *, output_dir: Path, benchmark_label: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_label = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in benchmark_label).strip("_")
    safe_label = safe_label or "eo002c_decision_report"
    json_path = output_dir / f"{safe_label}_decision_report.json"
    md_path = output_dir / f"{safe_label}_decision_report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")
    return json_path, md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EO-002C read-only metrics and decision report from EO-002B URL Finder validation JSON."
    )
    parser.add_argument("--benchmark-label", required=True)
    parser.add_argument("--report-json", action="append", default=[], help="Path to an EO-002B JSON report. Repeat for multiple reports.")
    parser.add_argument("--input-dir", type=Path, help="Directory containing EO-002B JSON reports. Defaults to the EO-002B export directory when omitted.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report_paths = discover_report_paths(args)
    if not report_paths:
        raise SystemExit(
            "No EO-002B JSON reports found. Pass --report-json or --input-dir, or run run_eo002b_url_finder_validation first."
        )
    missing = [str(path) for path in report_paths if not path.exists()]
    if missing:
        raise SystemExit("Missing EO-002B report(s): " + ", ".join(missing))

    directories = [str(path) for path in report_paths if path.is_dir()]
    if directories:
        raise SystemExit(
            "EO-002B report path points to a directory, not a JSON file: "
            + ", ".join(directories)
        )

    metrics = load_metrics_from_reports(report_paths)
    report = build_decision_report(
        metrics,
        benchmark_label=args.benchmark_label,
        source_reports=[str(path) for path in report_paths],
    )
    json_path, md_path = write_outputs(report, output_dir=args.output_dir, benchmark_label=args.benchmark_label)
    print("summary: " + json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    print(f"json_report_written: {json_path}")
    print(f"markdown_report_written: {md_path}")


if __name__ == "__main__":
    main()
