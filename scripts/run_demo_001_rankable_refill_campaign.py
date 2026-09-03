"""Refresh drifted live Product V1 assessments, then run the bounded DEMO-001 refill.

This is a narrow orchestration layer over existing reviewed writers. For the same
live Candidate-Fact-backed cohort used by the refill scout it may first apply the
existing revisions-audited assessment-detail refresh when the current employer-
origin vacancy fingerprint changed. It then delegates to the existing bounded
capability-fit -> canonical hard-filter -> ranking refill.

It never writes a hard-filter operator review, never overrides a deterministic
hard-filter result and never forces rank, Top-5, application or submission state.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

import psycopg
from psycopg.rows import dict_row

from scripts import run_product_v1_assessment_detail_refresh as assessment_refresh
from scripts.run_demo_001_rankable_refill_apply import (
    APPROVAL_TOKEN as REFILL_APPROVAL_TOKEN,
)
from scripts.run_demo_001_rankable_refill_apply import _selected_candidates
from scripts.run_demo_001_rankable_refill_scout import (
    _load_candidate_facts,
    _load_rows,
    scout,
)
from scripts.run_product_v1_assessment_materialization import (
    authorized_recurring_employer_origin_sources,
)
from src.config import get_database_config
from src.ingestion.repository import JobIngestionRepository
from src.search_intelligence.product_v1_downstream_preview import (
    fetch_public_https_detail_text,
)

APPROVAL_TOKEN = "DEMO-001-RANKABLE-REFILL-CAMPAIGN-001"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-cap", type=int, default=7)
    parser.add_argument("--target-rankable", type=int, default=5)
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    return parser


def _selected(candidate_cap: int) -> list[dict[str, object]]:
    authorized = sorted(
        authorized_recurring_employer_origin_sources(JobIngestionRepository())
    )
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        facts = _load_candidate_facts(conn)
        rows = _load_rows(
            conn,
            authorized_sources=authorized,
            limit=max(30, candidate_cap * 4),
        )
        conn.rollback()
    return _selected_candidates(scout(rows=rows, facts=facts), candidate_cap=candidate_cap)


def _refresh_selected(
    selected: list[dict[str, object]],
    *,
    apply: bool,
    applied_by: str,
) -> tuple[int, int]:
    authorized = sorted(
        authorized_recurring_employer_origin_sources(JobIngestionRepository())
    )
    planned = 0
    changed = 0
    for selected_row in selected:
        if str(selected_row.get("product_readiness_status") or "") == "rankable":
            print(f"REFRESH={selected_row['silver_job_id']}|SKIP|already_rankable")
            continue
        job_id = int(selected_row["silver_job_id"])
        with assessment_refresh.connect() as conn:
            assessment_refresh.ensure_schema(conn)
            row = assessment_refresh.load_current_row(conn, silver_job_id=job_id)
            final_url, _page_title, detail_text = fetch_public_https_detail_text(
                str(row["source_url"])
            )
            plan = assessment_refresh.build_refresh_plan(
                row=row,
                authorized_sources=authorized,
                final_url=final_url,
                detail_text=detail_text,
            )
            conn.rollback()
            if plan.would_change:
                planned += 1
            if apply and plan.would_change:
                did_change = assessment_refresh.apply_refresh(
                    conn,
                    expected_plan=plan,
                    authorized_sources=authorized,
                    applied_by=applied_by,
                )
                conn.commit()
                changed += int(did_change)
            print(
                "REFRESH="
                f"{job_id}|would_change={str(plan.would_change).lower()}|"
                f"changed={str(bool(apply and plan.would_change)).lower()}|"
                f"{plan.previous_detail_sha256[:12]}->{plan.next_detail_sha256[:12]}"
            )
    return planned, changed


def _run_refill(args: argparse.Namespace) -> None:
    command = [
        sys.executable,
        "-m",
        "scripts.run_demo_001_rankable_refill_apply",
        "--candidate-cap",
        str(args.candidate_cap),
        "--target-rankable",
        str(args.target_rankable),
        "--reviewed-by",
        str(args.reviewed_by),
    ]
    if args.apply:
        command.extend(
            [
                "--apply",
                "--approval-token",
                REFILL_APPROVAL_TOKEN,
            ]
        )
    subprocess.run(command, check=True)


def main() -> int:
    args = build_parser().parse_args()
    if not 1 <= args.candidate_cap <= 15:
        raise SystemExit("--candidate-cap must be between 1 and 15")
    if not 1 <= args.target_rankable <= 25:
        raise SystemExit("--target-rankable must be between 1 and 25")
    reviewed_by = str(args.reviewed_by or "").strip()
    if not reviewed_by:
        raise SystemExit("--reviewed-by must not be blank")
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit("invalid DEMO-001 refill campaign approval token")

    selected = _selected(args.candidate_cap)
    if not selected:
        raise SystemExit("no live Candidate-Fact-backed refill candidates")

    print("=== DEMO-001 REFILL CAMPAIGN ===")
    print(f"MODE={'apply' if args.apply else 'plan'}")
    print(f"SELECTED={len(selected)}")
    planned, changed = _refresh_selected(
        selected,
        apply=args.apply,
        applied_by=reviewed_by,
    )
    print(f"ASSESSMENT_REFRESH_PLANNED={planned}")
    print(f"ASSESSMENT_REFRESH_CHANGED={changed}")
    print("HARD_FILTER_OPERATOR_REVIEW_WRITES=0")
    print("PROVIDER_REQUESTS=0")

    if not args.apply and planned:
        print("REFILL_DEFERRED=assessment_refresh_apply_required")
        print("DEMO_001_RANKABLE_REFILL_CAMPAIGN=PLAN_COMPLETE")
        return 0

    _run_refill(args)
    print("DEMO_001_RANKABLE_REFILL_CAMPAIGN=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
