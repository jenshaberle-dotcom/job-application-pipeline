from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import get_database_config  # noqa: E402
from src.search_intelligence.generic008_stop_control_evidence_registry import (  # noqa: E402
    StopControlEvidenceReviewInput,
    build_stop_control_evidence_review_plan,
    fetch_accepted_stop_control_evidence_rows,
    insert_stop_control_evidence_review,
    render_plan_markdown,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or inspect DB-backed GENERIC-008 stop-control evidence reviews.")
    parser.add_argument("--list", action="store_true", help="List accepted DB-backed stop-control evidence rows and exit.")
    parser.add_argument("--company-name", help="Reviewed no-actionable/safe-stop company name. Required unless --list is used.")
    parser.add_argument("--company-key", default=None, help="Optional explicit normalized company key. Defaults to normalized company name.")
    parser.add_argument(
        "--review-action",
        default="no_useful_external_hint_no_candidate_creation",
        help="Safe-stop review action.",
    )
    parser.add_argument("--evidence-strength", default="none", help="Stop-control evidence strength.")
    parser.add_argument("--evidence-summary", help="Operator-written evidence summary. Required unless --list is used.")
    parser.add_argument("--reviewer", help="Reviewer name. Required unless --list is used.")
    parser.add_argument("--review-date", default=None, help="ISO date YYYY-MM-DD. Defaults to today's date for dry-run/write.")
    parser.add_argument("--source-reference", default=None, help="Optional DB/source reference for the review.")
    parser.add_argument("--write", action="store_true", help="Persist the reviewed evidence row to stop_control_evidence_reviews.")
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/generic008_stop_control_evidence_registry"),
        help="Output directory for JSON/Markdown review artifacts. These are reports only, never process inputs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.list:
        return _list_rows()

    missing = [
        name
        for name, value in {
            "company-name": args.company_name,
            "evidence-summary": args.evidence_summary,
            "reviewer": args.reviewer,
        }.items()
        if not value
    ]
    if missing:
        print("input_status=input_missing")
        print("missing_required_args=" + ",".join(missing))
        print("write=False")
        return 2

    review_date = args.review_date or date.today().isoformat()
    plan = build_stop_control_evidence_review_plan(
        StopControlEvidenceReviewInput(
            company_name=args.company_name,
            company_key=args.company_key,
            review_action=args.review_action,
            evidence_strength=args.evidence_strength,
            evidence_summary=args.evidence_summary,
            reviewer=args.reviewer,
            review_date=review_date,
            source_reference=args.source_reference,
        )
    )
    outputs = _write_outputs(plan.as_dict(), render_plan_markdown(plan), args.export_dir)

    inserted_id: int | None = None
    if args.write:
        if not plan.insert_allowed:
            print("input_status=invalid")
            print(f"insert_allowed={plan.insert_allowed}")
            print(f"validation_errors={list(plan.validation_errors)}")
            print("write=False")
            print(f"json={outputs['json']}")
            print(f"markdown={outputs['markdown']}")
            return 2
        import psycopg

        with psycopg.connect(**get_database_config()) as conn:
            inserted_id = insert_stop_control_evidence_review(conn, plan)
            conn.commit()

    print("# GENERIC-008 Stop-Control Evidence Registry")
    print("boundary=dry-run by default; --write is limited to stop_control_evidence_reviews only; no candidates, gates, connectors, Bronze/Silver/Gold, scheduler, CSV/Excel/export inputs")
    print(f"insert_allowed={plan.insert_allowed}")
    print(f"write={args.write}")
    if inserted_id is not None:
        print(f"stop_control_evidence_review_id={inserted_id}")
    print(f"action={plan.action}")
    print(f"reason={plan.reason}")
    print(f"validation_errors={list(plan.validation_errors)}")
    print(f"company_key={plan.row.get('company_key')}")
    print(f"company_name={plan.row.get('company_name')}")
    print(f"review_action={plan.row.get('review_action')}")
    print(f"json={outputs['json']}")
    print(f"markdown={outputs['markdown']}")
    return 0


def _list_rows() -> int:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        rows = fetch_accepted_stop_control_evidence_rows(conn)
    print("# GENERIC-008 Accepted Stop-Control Evidence Rows")
    print(f"row_count={len(rows)}")
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))
    return 0


def _write_outputs(report: dict[str, object], markdown: str, export_dir: Path) -> dict[str, str]:
    export_dir.mkdir(parents=True, exist_ok=True)
    json_path = export_dir / "generic008_stop_control_evidence_registry.json"
    md_path = export_dir / "generic008_stop_control_evidence_registry.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


if __name__ == "__main__":
    raise SystemExit(main())
