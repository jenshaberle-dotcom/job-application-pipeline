from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.generic006_stop_control_capture_repair_packet import (  # noqa: E402
    build_stop_control_capture_repair_packet,
    find_latest_generic004_report,
    find_latest_generic005_report,
    load_generic004_report,
    load_generic005_report,
    write_outputs,
)
from src.search_intelligence.generic008_stop_control_evidence_registry import (  # noqa: E402
    fetch_accepted_stop_control_evidence_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GENERIC-006 stop-control evidence repair packet.")
    parser.add_argument(
        "--generic004-input",
        type=Path,
        default=None,
        help="GENERIC-004 stop-control capture plan JSON. Defaults to latest exports/generic004... report.",
    )
    parser.add_argument(
        "--generic005-input",
        type=Path,
        default=None,
        help="GENERIC-005 final rerun JSON. Defaults to latest exports/generic005... report.",
    )
    # No --capture-input: GENERIC-006 must not read CSV/Excel/export files as operator input.
    parser.add_argument(
        "--disable-db-stop-control-evidence",
        action="store_true",
        help="Do not attempt to read DB-backed GENERIC-008 stop-control evidence. Intended for isolated tests only.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/generic006_stop_control_capture_repair_packet"),
        help="Output directory for JSON/Markdown repair packet artifacts. No CSV/Excel/export input is generated.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generic004_path = args.generic004_input or find_latest_generic004_report()
    if generic004_path is None:
        print("input_status=input_missing")
        print("input_warning=No GENERIC-004 report found under exports/generic004_stop_control_evidence_capture_plan*")
        return 2

    generic005_path = args.generic005_input or find_latest_generic005_report()
    if generic005_path is None:
        print("input_status=input_missing")
        print("input_warning=No GENERIC-005 report found under exports/generic005_stop_control_final_rerun*")
        return 2

    generic004_report = load_generic004_report(generic004_path)
    db_rows, db_status = load_db_stop_control_evidence_rows(disabled=args.disable_db_stop_control_evidence)
    stop_control_rows = db_rows if db_rows else None
    stop_control_source = "stop_control_evidence_reviews" if db_rows else "generic004_report_stop_control_evidence_requirements"
    report = build_stop_control_capture_repair_packet(
        generic004_report,
        load_generic005_report(generic005_path),
        stop_control_rows,
        generic004_path=str(generic004_path),
        generic005_path=str(generic005_path),
        stop_control_source=stop_control_source,
        database_reads=(not args.disable_db_stop_control_evidence),
    )
    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})

    print("# GENERIC-006 Stop-Control Capture Repair Packet")
    print("input_status=ok")
    print(f"generic004_input={generic004_path}")
    print(f"generic005_input={generic005_path}")
    print(f"db_stop_control_evidence_status={db_status}")
    print(f"stop_control_source={stop_control_source}")
    print(f"overall_status={report.get('overall_status')}")
    for key in [
        "capture_row_count",
        "ready_for_generic005_rerun_count",
        "blocked_capture_row_count",
        "missing_or_invalid_field_counts",
        "generic005_final_gap_ids",
        "safe_rerun_command_available",
    ]:
        print(f"{key}={summary.get(key)}")
    print(f"next_action={report.get('next_action')}")
    print(f"json={outputs['json']}")
    print(f"markdown={outputs['markdown']}")
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
