from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.generic005_stop_control_final_rerun import (  # noqa: E402
    build_stop_control_final_rerun_report,
    find_latest_expand003_report,
    find_latest_generic003_report,
    find_latest_generic004_report,
    load_expand003_report,
    load_generic003_report,
    load_generic004_report,
    write_outputs,
)
from src.search_intelligence.generic008_stop_control_evidence_registry import (  # noqa: E402
    fetch_accepted_stop_control_evidence_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GENERIC-005 stop-control evidence final rerun review.")
    parser.add_argument(
        "--generic003-input",
        type=Path,
        default=None,
        help="GENERIC-003 benchmark control rerun JSON. Defaults to latest exports/generic003... report.",
    )
    parser.add_argument(
        "--generic004-input",
        type=Path,
        default=None,
        help="GENERIC-004 stop-control capture plan JSON. Defaults to latest exports/generic004... report.",
    )
    parser.add_argument(
        "--expand003-input",
        type=Path,
        default=None,
        help="EXPAND-003 candidate review delta JSON. Defaults to latest exports/expand003... report.",
    )
    # No --capture-input: GENERIC-005 must not read CSV/Excel/export files as operator input.
    parser.add_argument(
        "--disable-db-stop-control-evidence",
        action="store_true",
        help="Do not attempt to read DB-backed GENERIC-008 stop-control evidence. Intended for isolated tests only.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/generic005_stop_control_final_rerun"),
        help="Output directory for JSON/Markdown and nested GENERIC-001 final rerun artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generic003_path = args.generic003_input or find_latest_generic003_report()
    if generic003_path is None:
        print("input_status=input_missing")
        print("input_warning=No GENERIC-003 report found under exports/generic003_benchmark_control_rerun_review*")
        return 2

    generic004_path = args.generic004_input or find_latest_generic004_report()
    if generic004_path is None:
        print("input_status=input_missing")
        print("input_warning=No GENERIC-004 report found under exports/generic004_stop_control_evidence_capture_plan*")
        return 2

    expand003_path = args.expand003_input or find_latest_expand003_report()
    if expand003_path is None:
        print("input_status=input_missing")
        print("input_warning=No EXPAND-003 report found under exports/expand003_candidate_review_delta_report*")
        return 2

    generic004_report = load_generic004_report(generic004_path)
    db_rows, db_status = load_db_stop_control_evidence_rows(disabled=args.disable_db_stop_control_evidence)
    stop_control_rows = db_rows if db_rows else None
    stop_control_source = "stop_control_evidence_reviews" if db_rows else "generic004_report_stop_control_evidence_requirements"
    report = build_stop_control_final_rerun_report(
        load_generic003_report(generic003_path),
        generic004_report,
        load_expand003_report(expand003_path),
        stop_control_rows,
        generic003_path=str(generic003_path),
        generic004_path=str(generic004_path),
        expand003_path=str(expand003_path),
        stop_control_source=stop_control_source,
        database_reads=(not args.disable_db_stop_control_evidence),
    )
    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})

    print("# GENERIC-005 Stop-Control Evidence / GENERIC-001 Final Rerun")
    print("input_status=ok")
    print(f"generic003_input={generic003_path}")
    print(f"generic004_input={generic004_path}")
    print(f"expand003_input={expand003_path}")
    print(f"db_stop_control_evidence_status={db_status}")
    print(f"stop_control_source={stop_control_source}")
    print(f"overall_status={report.get('overall_status')}")
    for key in [
        "positive_control_keys",
        "negative_control_keys",
        "accepted_stop_control_count",
        "rejected_stop_control_count",
        "closed_stop_gap_ids",
        "final_gap_ids",
        "generic001_final_overall_status",
        "generic001_final_failed_check_count",
    ]:
        print(f"{key}={summary.get(key)}")
    print(f"next_action={report.get('next_action')}")
    print(f"json={outputs['json']}")
    print(f"markdown={outputs['markdown']}")
    print(f"generic001_final_json={outputs['generic001_final_json']}")
    return 0


def load_db_stop_control_evidence_rows(*, disabled: bool) -> tuple[list[dict[str, object]], str]:
    if disabled:
        return [], "disabled"
    try:
        import psycopg
        from psycopg.rows import dict_row

        from src.config import get_database_config

        with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
            rows = fetch_accepted_stop_control_evidence_rows(conn)
        return rows, f"ok_row_count_{len(rows)}"
    except Exception as exc:  # pragma: no cover - defensive for local environments without DB.
        return [], f"unavailable_{type(exc).__name__}"


if __name__ == "__main__":
    raise SystemExit(main())
