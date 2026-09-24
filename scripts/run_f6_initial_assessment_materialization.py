"""Guarded F6 initial Product assessment materialization gate.

This entry point turns an already-qualified read-only materialization proposal into
one explicitly approved insert. It is intentionally narrower than the generic
materializer: exactly one Silver job, exactly one frozen fingerprint, insert-only,
and mandatory post-write proof.

It never grants hard-filter, capability-fit, ranking, Top-5, application,
submission or send authority.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from scripts import run_product_v1_assessment_materialization as materializer
from scripts import run_product_v1_assessment_materialization_resilient as resilient
from src.config import get_database_config
from src.ingestion.repository import JobIngestionRepository


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".runtime" / "demo" / "f6_initial_assessment_materialization.json"
APPROVAL_TOKEN = "F6-INITIAL-ASSESSMENT-MATERIALIZE"
REPORT_SCHEMA = "job_application_pipeline.f6_initial_assessment_materialization.v1"


class F6InitialAssessmentStop(RuntimeError):
    """Fail-closed F6 initial-assessment authority boundary."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise F6InitialAssessmentStop(message)


def _safe_plan(plan: Mapping[str, object]) -> dict[str, object]:
    proposals = [
        item
        for item in (plan.get("proposals") or [])
        if isinstance(item, Mapping)
    ]
    return {
        "schema": plan.get("schema"),
        "mode": plan.get("mode"),
        "ranking_policy_version": plan.get("ranking_policy_version"),
        "job_evidence_policy_version": plan.get("job_evidence_policy_version"),
        "candidate_count": plan.get("candidate_count"),
        "proposal_count": plan.get("proposal_count"),
        "blocked_count": plan.get("blocked_count"),
        "proposals": [
            {
                "silver_job_id": item.get("silver_job_id"),
                "source_name": item.get("source_name"),
                "title": item.get("title"),
                "materialization_fingerprint": item.get("materialization_fingerprint"),
                "origin_validation_status": (
                    (item.get("assessment") or {}).get("origin_validation_status")
                    if isinstance(item.get("assessment"), Mapping)
                    else None
                ),
                "activity_status": (
                    (item.get("assessment") or {}).get("activity_status")
                    if isinstance(item.get("assessment"), Mapping)
                    else None
                ),
                "hard_filter_status": (
                    (item.get("assessment") or {}).get("hard_filter_status")
                    if isinstance(item.get("assessment"), Mapping)
                    else None
                ),
                "capability_fit_status": (
                    (item.get("assessment") or {}).get("capability_fit_status")
                    if isinstance(item.get("assessment"), Mapping)
                    else None
                ),
                "unresolved_fields": item.get("unresolved_fields"),
            }
            for item in proposals
        ],
        "boundaries": dict(plan.get("boundaries") or {}),
    }


def build_exact_plan(
    *,
    silver_job_id: int,
) -> tuple[dict[str, object], set[str]]:
    repository = JobIngestionRepository()
    authorized_sources = materializer.authorized_recurring_employer_origin_sources(repository)

    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        ranking_policy_version, hard_filter_policy_version = materializer._load_policy_versions(conn)
        rows = materializer.select_rows(
            materializer._load_candidate_rows(
                conn,
                source_names=(),
                silver_job_ids=(silver_job_id,),
            ),
            role_relevant_only=False,
        )
        conn.rollback()

    plan = resilient.build_plan_isolated(
        rows=rows,
        authorized_sources=authorized_sources,
        ranking_policy_version=ranking_policy_version,
        hard_filter_policy_version=hard_filter_policy_version,
    )
    _require(int(plan.get("candidate_count") or 0) == 1, "exactly one F6 candidate is required")
    _require(int(plan.get("proposal_count") or 0) == 1, "exactly one F6 proposal is required")
    _require(int(plan.get("blocked_count") or 0) == 0, "F6 proposal must have zero blockers")
    proposals = plan.get("proposals")
    _require(isinstance(proposals, list) and len(proposals) == 1, "F6 proposal payload is invalid")
    proposal = proposals[0]
    _require(isinstance(proposal, Mapping), "F6 proposal payload is malformed")
    _require(int(proposal.get("silver_job_id") or 0) == silver_job_id, "F6 Silver identity drift")
    return dict(plan), authorized_sources


def verify_frozen_fingerprint(
    plan: Mapping[str, object],
    *,
    silver_job_id: int,
    expected_fingerprint: str,
) -> None:
    fingerprints = materializer._plan_fingerprints(plan)
    _require(
        fingerprints == {silver_job_id: expected_fingerprint},
        "F6 frozen materialization fingerprint mismatch",
    )


def postwrite_proof(
    *,
    silver_job_id: int,
    expected_policy_version: str,
) -> dict[str, object]:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                """
                SELECT
                    assessment.silver_job_id,
                    assessment.origin_validation_status,
                    assessment.activity_status,
                    assessment.hard_filter_status,
                    assessment.capability_fit_status,
                    assessment.profile_direction_score,
                    assessment.data_focus_score,
                    assessment.reliability_focus_score,
                    assessment.evidence_quality_score,
                    assessment.overall_quality_score,
                    assessment.policy_version,
                    assessment.assessed_by,
                    readiness.product_readiness_status,
                    readiness.lifecycle_status,
                    readiness.lifecycle_evidence_reason
                FROM job_product_assessments assessment
                JOIN gold_product_v1_job_readiness readiness
                  ON readiness.silver_job_id = assessment.silver_job_id
                WHERE assessment.silver_job_id = %s
                """,
                (silver_job_id,),
            )
            row = cur.fetchone()
        conn.rollback()

    _require(row is not None, "F6 post-write assessment row is missing")
    payload = dict(row)
    _require(payload.get("origin_validation_status") == "validated", "Origin validation did not persist")
    _require(payload.get("activity_status") == "active", "active assessment state did not persist")
    _require(payload.get("hard_filter_status") == "unknown", "hard-filter authority changed unexpectedly")
    _require(payload.get("capability_fit_status") == "unknown", "capability-fit authority changed unexpectedly")
    for field in (
        "profile_direction_score",
        "data_focus_score",
        "reliability_focus_score",
        "evidence_quality_score",
        "overall_quality_score",
    ):
        _require(payload.get(field) is None, f"ranking score authority appeared unexpectedly: {field}")
    _require(
        str(payload.get("policy_version") or "") == expected_policy_version,
        "job-evidence policy binding changed after write",
    )
    _require(
        str(payload.get("assessed_by") or "") == materializer.ASSESSED_BY,
        "unexpected assessment authority writer",
    )
    _require(
        payload.get("product_readiness_status") == "hard_filter_evidence_required",
        "post-write readiness did not stop at hard-filter evidence",
    )
    return materializer._json_safe(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silver-job-id", type=int, required=True)
    parser.add_argument("--expected-fingerprint", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _require(args.silver_job_id > 0, "Silver job id must be positive")
    _require(len(args.expected_fingerprint.strip()) == 64, "expected fingerprint must be SHA-256 length")
    if args.apply:
        _require(args.approval_token == APPROVAL_TOKEN, "invalid F6 approval token")
    else:
        _require(args.approval_token in (None, ""), "approval token is apply-only")

    plan, authorized_sources = build_exact_plan(silver_job_id=args.silver_job_id)
    verify_frozen_fingerprint(
        plan,
        silver_job_id=args.silver_job_id,
        expected_fingerprint=args.expected_fingerprint.strip(),
    )

    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "mode": "plan",
        "silver_job_id": args.silver_job_id,
        "expected_fingerprint": args.expected_fingerprint.strip(),
        "preflight": _safe_plan(plan),
        "boundaries": {
            "database_writes": False,
            "assessment_insert_max": 1,
            "assessment_updates": False,
            "capability_fit_created": False,
            "ranking_scores_created": False,
            "top5_forced": False,
            "application_or_submission_writes": False,
            "provider_or_llm_requests": 0,
        },
    }

    if args.apply:
        original_build_plan = materializer.build_plan
        materializer.build_plan = resilient.build_plan_isolated
        try:
            applied = materializer.apply_plan(
                plan=plan,
                source_names=(),
                silver_job_ids=(args.silver_job_id,),
                role_relevant_only=False,
                authorized_sources=authorized_sources,
            )
        finally:
            materializer.build_plan = original_build_plan

        _require(int(applied.get("inserted") or 0) == 1, "F6 Apply did not insert exactly one assessment")
        _require(
            int(applied.get("already_materialized") or 0) == 0,
            "F6 Apply encountered a pre-existing assessment",
        )
        proof = postwrite_proof(
            silver_job_id=args.silver_job_id,
            expected_policy_version=str(plan.get("job_evidence_policy_version") or ""),
        )
        report["mode"] = "apply"
        report["apply_result"] = {
            "inserted": applied.get("inserted"),
            "already_materialized": applied.get("already_materialized"),
        }
        report["postwrite_proof"] = proof
        report["boundaries"] = {
            **dict(report["boundaries"]),
            "database_writes": True,
            "assessment_rows_inserted": 1,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("============================================")
    print("F6 INITIAL ASSESSMENT MATERIALIZATION")
    print("============================================")
    print(f"MODE={report['mode']}")
    print(f"SILVER_JOB_ID={args.silver_job_id}")
    print(f"FINGERPRINT={args.expected_fingerprint.strip()}")
    print(f"RANKING_POLICY_VERSION={plan['ranking_policy_version']}")
    print(f"JOB_EVIDENCE_POLICY_VERSION={plan['job_evidence_policy_version']}")
    print("PREFLIGHT=PASS")
    if args.apply:
        proof = report["postwrite_proof"]
        print("INSERTED=1")
        print(f"ORIGIN_VALIDATION_STATUS={proof['origin_validation_status']}")
        print(f"ACTIVITY_STATUS={proof['activity_status']}")
        print(f"HARD_FILTER_STATUS={proof['hard_filter_status']}")
        print(f"CAPABILITY_FIT_STATUS={proof['capability_fit_status']}")
        print(f"PRODUCT_READINESS_STATUS={proof['product_readiness_status']}")
        print("POSTWRITE_PROOF=PASS")
    print("PROVIDER_REQUESTS=0")
    print("RANKING_SCORES_CREATED=0")
    print("TOP5_FORCED=0")
    print(f"artifact={args.output.resolve()}")
    print("F6_INITIAL_ASSESSMENT_MATERIALIZATION=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
