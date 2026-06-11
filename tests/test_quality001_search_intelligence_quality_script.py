from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_quality001_script_writes_bootstrap_report(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_quality001_search_intelligence_quality_review.py",
            "--output-dir",
            str(tmp_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "assumption_inventory_count=4" in result.stdout
    json_files = sorted(tmp_path.glob("quality001_search_intelligence_quality_review_*.json"))
    md_files = sorted(tmp_path.glob("quality001_search_intelligence_quality_review_*.md"))
    assert len(json_files) == 1
    assert len(md_files) == 1
    report = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert report["next_action"] == "run_quality001_with_current_sensor_funnel_and_stepstone_inputs"
    assert report["safety_boundary"]["external_requests"] is False


def test_quality001_script_can_read_sensor001h_json(tmp_path: Path) -> None:
    sensor_report = tmp_path / "sensor001h.json"
    sensor_report.write_text(
        json.dumps(
            {
                "overall_status": "monitoring_ready_with_observed_runs",
                "metric_summary": {
                    "ingestion_run_count": 1,
                    "total_loaded": 4,
                    "inserted_count": 1,
                    "duplicate_count": 3,
                    "failed_run_count": 0,
                    "observed_terms": ["Data Engineer"],
                },
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_quality001_search_intelligence_quality_review.py",
            "--sensor001h-json",
            str(sensor_report),
            "--output-dir",
            str(tmp_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "sensor_effectiveness_level=observed_incremental_yield" in result.stdout
    assert "inserted_share_percent=25.0" in result.stdout
