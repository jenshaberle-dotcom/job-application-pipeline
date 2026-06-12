from __future__ import annotations

from pathlib import Path

from src.search_intelligence.report_csv001_boundary import (
    REVIEW_OUTPUT_MARKER,
    build_csv_boundary_report,
)


def test_boundary_rejects_exports_csv_reads(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "bad.py").write_text('import pandas as pd\ndf = pd.read_csv("exports/report.csv")\n', encoding="utf-8")

    report = build_csv_boundary_report(repo_root=tmp_path, scan_roots=["scripts"])

    assert report["overall_status"] == "fail"
    assert report["summary"]["disallowed_export_csv_read_count"] == 1
    assert report["safety_boundary"]["csv_as_pipeline_input_allowed"] is False


def test_boundary_allows_marked_review_output_reference_without_read(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "producer.py").write_text(
        f'csv_path = export_dir / "review_{REVIEW_OUTPUT_MARKER}.csv"\n',
        encoding="utf-8",
    )

    report = build_csv_boundary_report(repo_root=tmp_path, scan_roots=["src"], strict_unmarked_exports=True)

    assert report["overall_status"] == "pass"
    assert report["summary"]["unmarked_export_csv_reference_count"] == 0


def test_boundary_warns_for_unmarked_export_csv_reference_before_strict_mode(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "producer.py").write_text('csv_path = export_dir / "legacy.csv"\n', encoding="utf-8")

    report = build_csv_boundary_report(repo_root=tmp_path, scan_roots=["src"])

    assert report["overall_status"] == "warning"
    assert "unmarked_csv_export_reference" in report["warning_ids"]


def test_boundary_test_fixtures_do_not_count_as_runtime_export_reads(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_boundary.py").write_text(
        'def test_fixture():\n    fixture = "pd.read_csv(\\\"exports/report.csv\\\")"\n',
        encoding="utf-8",
    )

    report = build_csv_boundary_report(repo_root=tmp_path, scan_roots=["tests"])

    assert report["overall_status"] == "pass"
    assert report["summary"]["disallowed_export_csv_read_count"] == 0
