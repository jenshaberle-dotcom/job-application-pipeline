"""Refresh drifted live Product V1 assessments, then run the bounded rankable refill.

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
import json
from pathlib import Path
import subprocess
import sys

import psycopg
from psycopg.rows import dict_row

from scripts import run_product_v1_assessment_detail_refresh as assessment_refresh
from scripts.run_product_v1_rankable_refill_apply import (
    APPROVAL_TOKEN as REFILL_APPROVAL_TOKEN,
)
from scripts.run_product_v1_rankable_refill_apply import _selected_candidates
from scripts.run_product_v1_rankable_refill_scout import (
    _load_candidate_facts,
    _load_rows,
    scout,
)
from scripts.run_product_v1_assessment_materialization import (
    APPROVAL_TOKEN as MATERIALIZATION_APPROVAL_TOKEN,
    authorized_recurring_employer_origin_sources,
)
from src.config import get_database_config
from src.ingestion.repository import JobIngestionRepository
from src.search_intelligence.product_v1_downstream_preview import (
    fetch_public_https_detail_text,
)
from src.search_intelligence.product_v1_demo_learning_sample import (
    DEMO_REQUIRED_EMPLOYERS,
    select_demo_learning_sample,
)

APPROVAL_TOKEN = "PRODUCT-V1-RANKABLE-REFILL-CAMPAIGN-001"
MATERIALIZATION_OUTPUT = Path(
    ".runtime/product/product_v1_rankable_refill_materialization.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-cap", type=int, default=7)
    parser.add_argument("--target-rankable", type=int, default=5)
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--demo-learning-sample", action="store_true")
    return parser


def _selected(candidate_cap: int, *, demo_learning_sample: bool) -> list[dict[str, object]]:
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
            limit=100 if demo_learning_sample else max(30, candidate_cap * 4),
            demo_learning_sample=demo_learning_sample,
        )
        conn.rollback()
    scouted = scout(rows=rows, facts=facts)
    if demo_learning_sample:
        return select_demo_learning_sample(
            scouted,
            candidate_cap=candidate_cap,
            required_employers=DEMO_REQUIRED_EMPLOYERS,
        )
    return _selected_candidates(scouted, candidate_cap=candidate_cap)


def _materialize_missing(
    selected: list[dict[str, object]],
    *,
    apply: bool,
    demo_learning_sample: bool,
) -> tuple[int, int]:
    missing_ids = [
        int(row["silver_job_id"])
        for row in selected
        if str(row.get("product_readiness_status") or "") == "assessment_required"
    ]
    if not missing_ids:
        print("ASSESSMENT_MATERIALIZATION=SKIP|none_missing")
        return 0, 0

    command = [
        sys.executable,
        "-m",
        "scripts.run_product_v1_assessment_materialization",
    ]
    for job_id in missing_ids:
        command.extend(["--silver-job-id", str(job_id)])
    if not demo_learning_sample:
        command.append("--role-relevant-only")
    else:
        command.append("--demo-learning-sample")
    command.extend(
        [
            "--output",
            str(MATERIALIZATION_OUTPUT),
        ]
    )
    if apply:
        command.extend(
            [
                "--apply",
                "--approval-token",
                MATERIALIZATION_APPROVAL_TOKEN,
            ]
        )

    subprocess.run(command, check=True)
    payload = json.loads(MATERIALIZATION_OUTPUT.read_text(encoding="utf-8"))
    blocked = int(payload.get("blocked_count") or 0)
    proposals = int(payload.get("proposal_count") or 0)
    if blocked:
        raise SystemExit(
            f"assessment materialization blocked candidates: {blocked}"
        )
    if proposals != len(missing_ids):
        raise SystemExit(
            "assessment materialization candidate drift: "
            f"expected={len(missing_ids)} proposals={proposals}"
        )

    inserted = 0
    if apply:
        apply_result = payload.get("apply_result") or {}
        inserted = int(apply_result.get("inserted") or 0)
        already = int(apply_result.get("already_materialized") or 0)
        if inserted + already != len(missing_ids):
            raise SystemExit(
                "assessment materialization apply cardinality mismatch: "
                f"expected={len(missing_ids)} inserted={inserted} already={already}"
            )

    print(
        "ASSESSMENT_MATERIALIZATION="
        f"{'APPLY' if apply else 'PLAN'}|candidates={len(missing_ids)}|"
        f"proposals={proposals}|inserted={inserted}"
    )
    return proposals, inserted


def _refresh_selected(
    selected: list[dict[str, object]],
    *,
    apply: bool,
    applied_by: str,
    demo_learning_sample: bool,
) -> tuple[int, int]:
    authorized = (
        sorted({str(row["source_name"]) for row in selected})
        if demo_learning_sample
        else sorted(authorized_recurring_employer_origin_sources(JobIngestionRepository()))
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
        "scripts.run_product_v1_rankable_refill_apply",
        "--candidate-cap",
        str(args.candidate_cap),
        "--target-rankable",
        str(args.target_rankable),
        "--reviewed-by",
        str(args.reviewed_by),
    ]
    if args.demo_learning_sample:
        command.append("--demo-learning-sample")
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
        raise SystemExit("invalid Product V1 rankable-refill campaign approval token")

    selected = _selected(
        args.candidate_cap,
        demo_learning_sample=args.demo_learning_sample,
    )
    if not selected:
        raise SystemExit("no live Candidate-Fact-backed refill candidates")

    print("=== PRODUCT V1 RANKABLE REFILL CAMPAIGN ===")
    print(f"MODE={'apply' if args.apply else 'plan'}")
    print(f"SELECTED={len(selected)}")
    materialization_planned, materialized = _materialize_missing(
        selected,
        apply=args.apply,
        demo_learning_sample=args.demo_learning_sample,
    )
    print(f"ASSESSMENT_MATERIALIZATION_PLANNED={materialization_planned}")
    print(f"ASSESSMENT_MATERIALIZED={materialized}")

    if not args.apply and materialization_planned:
        print("REFILL_DEFERRED=assessment_materialization_apply_required")
        print("HARD_FILTER_OPERATOR_AUTO_PASS=0")
        print("PROVIDER_REQUESTS=0")
        print("PRODUCT_V1_RANKABLE_REFILL_CAMPAIGN=PLAN_COMPLETE")
        return 0

    planned, changed = _refresh_selected(
        selected,
        apply=args.apply,
        applied_by=reviewed_by,
        demo_learning_sample=args.demo_learning_sample,
    )
    print(f"ASSESSMENT_REFRESH_PLANNED={planned}")
    print(f"ASSESSMENT_REFRESH_CHANGED={changed}")
    print("HARD_FILTER_OPERATOR_AUTO_PASS=0")
    print("PROVIDER_REQUESTS=0")

    if not args.apply and planned:
        print("REFILL_DEFERRED=assessment_refresh_apply_required")
        print("PRODUCT_V1_RANKABLE_REFILL_CAMPAIGN=PLAN_COMPLETE")
        return 0

    _run_refill(args)
    print("PRODUCT_V1_RANKABLE_REFILL_CAMPAIGN=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
