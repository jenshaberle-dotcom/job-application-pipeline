#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.sensor001f_ba_remote_result_decision import (
    build_sensor001f_result_decision,
    latest_sensor001e_report_path,
    render_markdown,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build SENSOR-001F result decision from a SENSOR-001E bounded sample export without mutations."
    )
    parser.add_argument("--sensor001e-json", default=None, help="Path to a SENSOR-001E JSON export. Defaults to latest exports/sensor001e_*.json.")
    parser.add_argument("--output-dir", default="exports", help="Directory for JSON/Markdown decision artifacts.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path = Path(args.sensor001e_json) if args.sensor001e_json else latest_sensor001e_report_path(output_dir)
    upstream = json.loads(input_path.read_text(encoding="utf-8"))
    report = build_sensor001f_result_decision(upstream).as_dict()
    report["sensor001e_input_path"] = str(input_path)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"sensor001f_ba_remote_result_decision_{stamp}.json"
    md_path = output_dir / f"sensor001f_ba_remote_result_decision_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print("# SENSOR-001F BA Remote/Nationwide Result Decision")
    print(f"overall_status={report.get('overall_status')}")
    print(f"source_status={report.get('source_status')}")
    print(f"recommended_decision={report.get('recommended_decision')}")
    print(f"confidence={report.get('confidence')}")
    print(f"sensor001e_input_path={input_path}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
