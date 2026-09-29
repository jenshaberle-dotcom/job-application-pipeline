"""Reusable Product V1 assessment-cohort orchestration.

This is the product entrypoint for closing a bounded cohort from current,
Employer-Origin vacancy evidence through the existing Assessment -> Candidate Fit
-> hard-filter -> ranking authorities.  It deliberately reuses the already
qualified lower-level refill implementation while removing demo-specific target
semantics from the operator contract.

No job id, company or rank is hard-coded here.  Candidate selection is derived
from current Employer-Origin truth, target-role classification, approved Candidate
Facts and exact live vacancy evidence.

The command is plan-only by default.  Apply requires the product-specific approval
token and never directly writes Top-5 membership, lifecycle, source activation,
application or submission state.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Mapping

import psycopg
from psycopg.rows import dict_row

from scripts.product_v1_control_center_base import load_product_v1_payload
from scripts.run_product_v1_rankable_refill_apply import _selected_candidates
from scripts.run_product_v1_rankable_refill_campaign import (
    APPROVAL_TOKEN as RANKABLE_REFILL_APPROVAL_TOKEN,
)
from scripts.run_product_v1_rankable_refill_scout import (
    _load_candidate_facts,
    _load_rows,
    scout,
)
from scripts.run_product_v1_assessment_materialization import (
    authorized_recurring_employer_origin_sources,
)
from src.config import get_database_config
from src.ingestion.repository import JobIngestionRepository
from scripts.product_v1_job_presentation_runtime import (
    is_employer_origin_review_source,
)
from src.search_intelligence.product_v1_demo_learning_sample import (
    DEMO_REQUIRED_EMPLOYERS,
    select_demo_learning_sample,
)


SCHEMA = "job_application_pipeline.product_v1_assessment_cohort.v1"
APPROVAL_TOKEN = "PRODUCT-V1-ASSESSMENT-COHORT-001"
DEFAULT_OUTPUT = Path(".runtime/product/product_v1_assessment_cohort.json")
CONTROL_CENTER_REPORT = Path(".runtime/product/control_center_assessment_cohort.json")

_PERSISTENT_STATE_RAW = os.environ.get("JAP_CONTROL_CENTER_STATE_ROOT", "").strip()
_PROJECT_ROOT_RAW = os.environ.get("JAP_CONTROL_CENTER_PROJECT_ROOT", "").strip()
PERSISTENT_STATE_ROOT = (
    Path(_PERSISTENT_STATE_RAW).resolve() if _PERSISTENT_STATE_RAW else None
)
CANONICAL_PROJECT_ROOT = (
    Path(_PROJECT_ROOT_RAW).resolve() if _PROJECT_ROOT_RAW else None
)
FROZEN_DEMO_COHORT = (
    PERSISTENT_STATE_ROOT / "demo-learning-cohort-frozen.json"
    if PERSISTENT_STATE_ROOT is not None
    else Path(".runtime/product/demo_learning_cohort_frozen.json")
)


class ProductAssessmentCohortStop(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProductAssessmentCohortStop(message)


def _report_selection_ids(path: Path, candidate_cap: int) -> tuple[int, ...]:
    if not path.is_file():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ()
    if not isinstance(payload, Mapping):
        return ()
    if payload.get("schema") == "job_application_pipeline.demo_learning_cohort_frozen.v1":
        raw = payload.get("silver_job_ids")
    else:
        boundaries = payload.get("boundaries")
        selection = payload.get("selection")
        if not isinstance(boundaries, Mapping) or boundaries.get("demo_learning_sample") is not True:
            return ()
        if not isinstance(selection, Mapping):
            return ()
        jobs = selection.get("jobs")
        raw = [
            item.get("silver_job_id")
            for item in jobs
            if isinstance(item, Mapping)
        ] if isinstance(jobs, list) else []
    try:
        ids = tuple(dict.fromkeys(int(value) for value in raw or [] if int(value) > 0))
    except (TypeError, ValueError):
        return ()
    return ids if len(ids) == candidate_cap else ()


def _load_frozen_demo_ids(candidate_cap: int) -> tuple[tuple[int, ...], str | None]:
    candidates: list[Path] = [FROZEN_DEMO_COHORT]
    if CANONICAL_PROJECT_ROOT is not None:
        project_product = CANONICAL_PROJECT_ROOT / ".runtime" / "product"
        candidates.extend(
            [
                project_product / "demo_learning_cohort_frozen.json",
                project_product / "control_center_assessment_cohort.json",
                project_product / "product_v1_assessment_cohort.json",
            ]
        )
    candidates.extend([CONTROL_CENTER_REPORT, DEFAULT_OUTPUT])
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        ids = _report_selection_ids(path, candidate_cap)
        if ids:
            return ids, str(path)
    return (), None


def _write_frozen_demo_cohort(
    selected: list[dict[str, object]],
    *,
    recovered_from: str | None,
) -> None:
    payload = {
        "schema": "job_application_pipeline.demo_learning_cohort_frozen.v1",
        "silver_job_ids": [int(row["silver_job_id"]) for row in selected],
        "jobs": [
            {
                "silver_job_id": int(row["silver_job_id"]),
                "company_name": row.get("company_name"),
                "title": row.get("title"),
                "source_name": row.get("source_name"),
            }
            for row in selected
        ],
        "recovered_from": recovered_from,
        "boundaries": {
            "persistent_install_state": PERSISTENT_STATE_ROOT is not None,
            "immutable_runtime_payload_mutation": False,
            "job_ids_hard_coded_in_source": False,
            "automatic_replacement_on_drift": False,
        },
    }
    FROZEN_DEMO_COHORT.parent.mkdir(parents=True, exist_ok=True)
    FROZEN_DEMO_COHORT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _selection(
    candidate_cap: int,
    *,
    demo_learning_sample: bool,
    frozen_ids: tuple[int, ...] = (),
) -> tuple[list[dict[str, object]], dict[str, object]]:
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
            limit=100 if demo_learning_sample else max(60, candidate_cap * 5),
            demo_learning_sample=demo_learning_sample,
        )
        conn.rollback()

    scouted = scout(rows=rows, facts=facts)
    if demo_learning_sample and frozen_ids:
        _require(
            len(frozen_ids) == candidate_cap,
            "frozen demo cohort cardinality drift",
        )
        by_id = {int(row["silver_job_id"]): row for row in scouted}
        missing = sorted(set(frozen_ids) - set(by_id))
        _require(
            not missing,
            "frozen demo cohort jobs disappeared from current Product truth: "
            + ",".join(str(value) for value in missing),
        )
        selected = [dict(by_id[value]) for value in frozen_ids]
        for row in selected:
            _require(
                row.get("live_outcome") == "seen_active",
                f"frozen demo job is no longer live: {row['silver_job_id']}",
            )
            _require(
                row.get("geography_eligible") is True,
                f"frozen demo job left approved geography: {row['silver_job_id']}",
            )
            matches = row.get("candidate_fact_matches")
            _require(
                isinstance(matches, list) and bool(matches),
                f"frozen demo job lost Candidate Fact capability evidence: {row['silver_job_id']}",
            )
        selection_mode = "demo_learning_frozen"
    else:
        selected = (
            select_demo_learning_sample(
                scouted,
                candidate_cap=candidate_cap,
                required_employers=DEMO_REQUIRED_EMPLOYERS,
            )
            if demo_learning_sample
            else _selected_candidates(scouted, candidate_cap=candidate_cap)
        )
        selection_mode = "demo_learning_sample" if demo_learning_sample else "canonical"
    diagnostics = {
        "authorized_source_count": len(authorized),
        "approved_capability_fact_count": len(facts),
        "scouted_current_job_count": len(scouted),
        "live_active_count": sum(
            1 for row in scouted if row.get("live_outcome") == "seen_active"
        ),
        "role_relevant_count": sum(1 for row in scouted if row.get("role_relevant") is True),
        "geography_eligible_count": sum(
            1 for row in scouted if row.get("geography_eligible") is True
        ),
        "fact_match_count": sum(
            1 for row in scouted if int(row.get("matched_fact_count") or 0) > 0
        ),
        "selected_count": len(selected),
        "selection_mode": selection_mode,
        "frozen_selection": bool(demo_learning_sample and frozen_ids),
        "geography_buckets": {
            bucket: sum(
                1 for row in scouted if str(row.get("geography_bucket") or "") == bucket
            )
            for bucket in sorted(
                {
                    str(row.get("geography_bucket") or "")
                    for row in scouted
                    if str(row.get("geography_bucket") or "")
                }
            )
        },
    }
    return selected, diagnostics


def _run_existing_authorities(
    *,
    candidate_cap: int,
    top5_target: int,
    reviewed_by: str,
    apply: bool,
    demo_learning_sample: bool,
    selected_ids: tuple[int, ...] = (),
) -> int:
    command = [
        sys.executable,
        "-m",
        "scripts.run_product_v1_rankable_refill_campaign",
        "--candidate-cap",
        str(candidate_cap),
        "--target-rankable",
        str(top5_target),
        "--reviewed-by",
        reviewed_by,
    ]
    if demo_learning_sample:
        command.append("--demo-learning-sample")
    for job_id in selected_ids:
        command.extend(["--silver-job-id", str(job_id)])
    if apply:
        command.extend(
            [
                "--apply",
                "--approval-token",
                RANKABLE_REFILL_APPROVAL_TOKEN,
            ]
        )
    completed = subprocess.run(command, check=False)
    return int(completed.returncode)


def _current_product_truth(
    *,
    selected_ids: set[int],
) -> dict[str, object]:
    payload = load_product_v1_payload(include_source_connector_overview=False)
    jobs = [
        row
        for row in payload.get("job_readiness", [])
        if isinstance(row, Mapping)
        and str(row.get("lifecycle_status") or "") == "active_confirmed"
    ]
    selected = [
        row for row in jobs
        if int(row.get("silver_job_id") or 0) in selected_ids
        and is_employer_origin_review_source(row)
    ]
    selected_unique = {
        int(row["silver_job_id"]): row for row in selected
    }
    _require(len(selected_unique) == len(selected), "duplicate selected Product job identity")
    complete = [
        row
        for row in selected
        if str(row.get("profile_fit_coverage_status") or "") == "profile_fit_complete"
        and str(row.get("profile_fit_decision") or "") in {"passed", "failed"}
    ]
    complete_passed = [
        row for row in complete if str(row.get("profile_fit_decision") or "") == "passed"
    ]
    rankable = [
        row
        for row in selected
        if str(row.get("product_readiness_status") or "") == "rankable"
    ]
    candidate_fit_authoritative = [
        row
        for row in selected
        if str(row.get("candidate_fit_authority_status") or "") == "authoritative"
        and row.get("candidate_fit_score") is not None
    ]
    affinity_authoritative = [
        row
        for row in selected
        if str(row.get("affinity_authority_status") or "") == "authoritative"
        and row.get("affinity_score") is not None
    ]
    top = [row for row in payload.get("top_jobs", []) if isinstance(row, Mapping)]

    top_violations: list[dict[str, object]] = []
    top_ids = [int(row.get("silver_job_id") or 0) for row in top]
    if len(set(top_ids)) != len(top_ids) or any(job_id <= 0 for job_id in top_ids):
        top_violations.append({"reason": "invalid_or_duplicate_top_job_identity"})
    outside_cohort = sorted(job_id for job_id in top_ids if job_id not in selected_ids)
    if outside_cohort:
        top_violations.append(
            {
                "reason": "top_job_outside_selected_assessment_cohort",
                "silver_job_ids": outside_cohort,
            }
        )
    if sorted(int(row.get("product_rank") or 0) for row in top) != list(
        range(1, len(top) + 1)
    ):
        top_violations.append({"reason": "non_contiguous_top_job_ranks"})
    for row in top:
        if (
            str(row.get("lifecycle_status") or "") != "active_confirmed"
            or str(row.get("profile_fit_decision") or "") != "passed"
            or str(row.get("profile_fit_coverage_status") or "") != "profile_fit_complete"
            or str(row.get("hard_filter_status") or "") != "passed"
            or str(row.get("affinity_authority_status") or "") != "authoritative"
            or not is_employer_origin_review_source(row)
        ):
            top_violations.append(
                {
                    "silver_job_id": row.get("silver_job_id"),
                    "lifecycle_status": row.get("lifecycle_status"),
                    "profile_fit_coverage_status": row.get("profile_fit_coverage_status"),
                    "profile_fit_decision": row.get("profile_fit_decision"),
                    "hard_filter_status": row.get("hard_filter_status"),
                    "affinity_authority_status": row.get("affinity_authority_status"),
                    "source_name": row.get("source_name"),
                }
            )

    blocker_counts: dict[str, int] = {}
    for row in selected:
        key = str(row.get("product_readiness_status") or "unknown")
        blocker_counts[key] = blocker_counts.get(key, 0) + 1

    return {
        "current_job_count": len(jobs),
        "profile_fit_complete_count": len(complete),
        "profile_fit_passed_count": len(complete_passed),
        "rankable_job_count": len(rankable),
        "candidate_fit_authoritative_count": len(candidate_fit_authoritative),
        "affinity_authoritative_count": len(affinity_authoritative),
        "top_job_count": len(top),
        "selected_postflight_count": len(selected),
        "selected_readiness_counts": blocker_counts,
        "selected": [
            {
                "silver_job_id": int(row.get("silver_job_id") or 0),
                "company_name": row.get("company_name"),
                "title": row.get("title"),
                "source_name": row.get("source_name"),
                "profile_fit_coverage_status": row.get("profile_fit_coverage_status"),
                "profile_fit_decision": row.get("profile_fit_decision"),
                "profile_fit_missing_factors": row.get("profile_fit_missing_factors"),
                "profile_fit_factors": row.get("profile_fit_factors"),
                "candidate_fit_score": row.get("candidate_fit_score"),
                "candidate_fit_authority_status": row.get("candidate_fit_authority_status"),
                "candidate_fit_observed_job_skill_count": row.get("candidate_fit_observed_job_skill_count"),
                "candidate_fit_exact_match_count": row.get("candidate_fit_exact_match_count"),
                "hard_filter_status": row.get("hard_filter_status"),
                "product_readiness_status": row.get("product_readiness_status"),
                "affinity_score": row.get("affinity_score"),
                "affinity_authority_status": row.get("affinity_authority_status"),
            }
            for row in selected
        ],
        "top_jobs": [
            {
                "product_rank": row.get("product_rank"),
                "silver_job_id": row.get("silver_job_id"),
                "company_name": row.get("company_name"),
                "title": row.get("title"),
                "profile_fit_decision": row.get("profile_fit_decision"),
                "hard_filter_status": row.get("hard_filter_status"),
                "affinity_score": row.get("affinity_score"),
            }
            for row in top
        ],
        "top5_authority_violations": top_violations,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluated-target", type=int, default=10)
    parser.add_argument("--top5-target", type=int, default=5)
    parser.add_argument("--candidate-cap", type=int, default=10)
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--demo-learning-sample", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    _require(1 <= args.evaluated_target <= 25, "--evaluated-target must be between 1 and 25")
    _require(args.top5_target == 5, "--top5-target must be exactly 5")
    _require(
        args.candidate_cap == args.evaluated_target,
        "--candidate-cap must equal evaluated-target for the authoritative cohort",
    )
    reviewed_by = str(args.reviewed_by or "").strip()
    _require(bool(reviewed_by), "--reviewed-by must not be blank")
    if args.apply:
        _require(
            args.approval_token == APPROVAL_TOKEN,
            "invalid Product V1 assessment-cohort approval token",
        )

    frozen_ids: tuple[int, ...] = ()
    frozen_source: str | None = None
    if args.demo_learning_sample:
        frozen_ids, frozen_source = _load_frozen_demo_ids(args.candidate_cap)
    selected, selection_diagnostics = _selection(
        args.candidate_cap,
        demo_learning_sample=args.demo_learning_sample,
        frozen_ids=frozen_ids,
    )
    selected_id_tuple = tuple(int(row["silver_job_id"]) for row in selected)
    selected_ids = set(selected_id_tuple)
    if args.demo_learning_sample and args.apply and not FROZEN_DEMO_COHORT.is_file():
        _write_frozen_demo_cohort(selected, recovered_from=frozen_source)
    enough_candidates = len(selected) >= args.evaluated_target

    authority_exit = 0
    if enough_candidates:
        authority_exit = _run_existing_authorities(
            candidate_cap=args.candidate_cap,
            top5_target=args.top5_target,
            reviewed_by=reviewed_by,
            apply=args.apply,
            demo_learning_sample=args.demo_learning_sample,
            selected_ids=selected_id_tuple,
        )

    final = _current_product_truth(selected_ids=selected_ids)
    target_met = (
        enough_candidates
        and authority_exit == 0
        and int(final["profile_fit_complete_count"]) >= args.evaluated_target
        and int(final["candidate_fit_authoritative_count"]) >= args.evaluated_target
        and int(final["affinity_authoritative_count"]) >= args.evaluated_target
        and int(final["profile_fit_passed_count"]) >= args.top5_target
        and int(final["rankable_job_count"]) >= args.top5_target
        and int(final["top_job_count"]) == args.top5_target
        and not final["top5_authority_violations"]
    )

    report = {
        "schema": SCHEMA,
        "mode": "apply" if args.apply else "plan",
        "targets": {
            "evaluated_jobs": args.evaluated_target,
            "top5_jobs": args.top5_target,
            "candidate_cap": args.candidate_cap,
        },
        "selection": {
            "selected_count": len(selected),
            "enough_candidates": enough_candidates,
            "frozen": bool(args.demo_learning_sample),
            "frozen_source": frozen_source or ("new_runtime_freeze" if args.demo_learning_sample and args.apply else None),
            "jobs": [
                {
                    "silver_job_id": int(row["silver_job_id"]),
                    "company_name": row.get("company_name"),
                    "title": row.get("title"),
                    "source_name": row.get("source_name"),
                    "geography_bucket": row.get("geography_bucket"),
                    "matched_fact_count": row.get("matched_fact_count"),
                    "matched_capability_tags": row.get("matched_capability_tags"),
                }
                for row in selected
            ],
            "diagnostics": selection_diagnostics,
        },
        "authority_pipeline_exit_code": authority_exit,
        "final": final,
        "target_met": target_met,
        "boundaries": {
            "job_ids_hard_coded": False,
            "companies_hard_coded": False,
            "direct_top5_writes": False,
            "direct_rank_writes": False,
            "hard_filter_operator_auto_pass": False,
            "provider_or_llm_requests": 0,
            "selection_requires_current_employer_origin": True,
            "selection_requires_exact_live_vacancy": True,
            "selection_requires_approved_candidate_fact_match": True,
            "top5_must_be_subset_of_selected_ten": True,
            "candidate_fit_and_affinity_remain_separate": True,
            "candidate_fit_is_job_skills_vs_cv_skills": True,
            "numeric_candidate_fit_authority_created": True,
            "all_ten_require_numeric_candidate_fit": True,
            "all_ten_require_authoritative_affinity": True,
            "demo_cohort_frozen": bool(args.demo_learning_sample),
            "combined_score_authority_created": False,
            "demo_learning_sample": bool(args.demo_learning_sample),
            "canonical_role_classifier_unchanged": True,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("=== PRODUCT V1 ASSESSMENT COHORT ===")
    print(f"MODE={report['mode']}")
    print(f"SELECTED={len(selected)}")
    print(f"EVALUATED_TARGET={args.evaluated_target}")
    print(f"PROFILE_FIT_COMPLETE={final['profile_fit_complete_count']}")
    print(f"PROFILE_FIT_PASSED={final['profile_fit_passed_count']}")
    print(f"CANDIDATE_FIT_AUTHORITATIVE={final['candidate_fit_authoritative_count']}")
    print(f"AFFINITY_AUTHORITATIVE={final['affinity_authoritative_count']}")
    print(f"RANKABLE={final['rankable_job_count']}")
    print(f"TOP5={final['top_job_count']}")
    print(f"TARGET_MET={str(target_met).lower()}")
    print("DIRECT_TOP5_WRITES=0")
    print("DIRECT_RANK_WRITES=0")
    print("HARD_FILTER_OPERATOR_AUTO_PASS=0")
    print("PROVIDER_REQUESTS=0")
    print(f"artifact={args.output.resolve()}")

    if args.apply and not target_met:
        raise SystemExit("PRODUCT_V1_ASSESSMENT_COHORT_TARGET_NOT_MET")
    if authority_exit != 0:
        raise SystemExit(f"PRODUCT_V1_ASSESSMENT_COHORT_AUTHORITY_FAILED:{authority_exit}")
    if not enough_candidates:
        raise SystemExit(
            f"PRODUCT_V1_ASSESSMENT_COHORT_INSUFFICIENT_CANDIDATES:"
            f"{len(selected)}<{args.evaluated_target}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
