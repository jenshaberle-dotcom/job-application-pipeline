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

from src.search_intelligence.quality001_search_intelligence_quality import (
    build_quality001_report,
    render_markdown,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build QUALITY-001 Search Intelligence quality and recall report from existing read-only inputs."
    )
    parser.add_argument("--sensor001h-json", default=None, help="Optional SENSOR-001H JSON report path.")
    parser.add_argument("--output-dir", default="exports")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sensor001h_report = None
    if args.sensor001h_json:
        sensor001h_report = json.loads(Path(args.sensor001h_json).read_text(encoding="utf-8"))

    report = build_quality001_report(sensor001h_report=sensor001h_report).as_dict()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"quality001_search_intelligence_quality_review_{stamp}.json"
    md_path = output_dir / f"quality001_search_intelligence_quality_review_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print("# QUALITY-001 Search Intelligence Quality & Recall Foundation")
    print(f"next_action={report.get('next_action')}")
    sensor = report.get("sensor_effectiveness") or {}
    if sensor:
        print(f"sensor_effectiveness_level={sensor.get('effectiveness_level')}")
        print(f"inserted_share_percent={sensor.get('inserted_share_percent')}")
        print(f"duplicate_share_percent={sensor.get('duplicate_share_percent')}")
    print(f"assumption_inventory_count={len(report.get('assumption_inventory', []))}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
