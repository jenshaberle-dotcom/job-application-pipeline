from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.b1_diagnostic_foundation import (
    build_b1_diagnostic_foundation_report,
    render_markdown,
    sample_b1_inputs,
)


def main() -> int:
    inputs = sample_b1_inputs()
    report = build_b1_diagnostic_foundation_report(**inputs).as_dict()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    export_dir = Path("exports")
    export_dir.mkdir(exist_ok=True)
    json_path = export_dir / f"b1_diagnostic_foundation_{stamp}.json"
    md_path = export_dir / f"b1_diagnostic_foundation_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print("# B1 Diagnostic Foundation")
    print(f"status={report['sensor_001f']['status']}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
