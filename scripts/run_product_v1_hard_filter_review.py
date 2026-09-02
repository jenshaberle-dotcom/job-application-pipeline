from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.config import get_database_config


INPUT_SCHEMA = "job_application_pipeline.product_v1_hard_filter_review_input.v1"
REPORT_SCHEMA = "job_application_pipeline.product_v1_hard_filter_review.v1"
APPROVAL_TOKEN = "PRODUCT-V1-HARD-FILTER-REVIEW-001"
REVIEW_SCOPE = "resolve_unknown_source_evidence"
MIN_RATIONALE_LENGTH = 8


class HardFilterReviewStop(RuntimeError):
    """Fail closed when current product authority does not admit a review."""


@dataclass(frozen=True)
class ReviewRequest:
    silver_job_id: int
    decision: str
    rationale: str


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def parse_input(payload: Mapping[str, object]) -> tuple[ReviewRequest, ...]:
    if payload.get("schema") != INPUT_SCHEMA:
        raise HardFilterReviewStop("hard-filter review input schema is invalid")
    raw_reviews = payload.get("reviews")
    if not isinstance(raw_reviews, list) or not raw_reviews:
        raise HardFilterReviewStop("hard-filter review input requires reviews")

    reviews: list[ReviewRequest] = []
    seen: set[int] = set()
    for raw in raw_reviews:
        if not isinstance(raw, Mapping):
            raise HardFilterReviewStop("hard-filter review item must be an object")
        try:
            silver_job_id = int(raw.get("silver_job_id") or 0)
        except (TypeError, ValueError) as exc:
            raise HardFilterReviewStop("silver_job_id must be an integer") from exc
        if silver_job_id <= 0:
            raise HardFilterReviewStop("silver_job_id must be positive")
        if silver_job_id in seen:
            raise HardFilterReviewStop(f"duplicate silver_job_id: {silver_job_id}")
        seen.add(silver_job_id)

        decision = str(raw.get("decision") or "").strip().lower()
        if decision not in {"passed", "failed"}:
            raise HardFilterReviewStop(
                f"hard-filter review decision must be passed or failed: {silver_job_id}"
            )
        rationale = " ".join(str(raw.get("rationale") or "").split())
        if len(rationale) < MIN_RATIONALE_LENGTH:
            raise HardFilterReviewStop(
                f"hard-filter review rationale is too short: {silver_job_id}"
            )
        reviews.append(
            ReviewRequest(
                silver_job_id=silver_job_id,
                decision=decision,
                rationale=rationale,
            )
        )
    return tuple(reviews)


def ensure_schema(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        for relation in (
            "product_v1_hard_filter_reviews",
            "gold_product_v1_hard_filter_evaluation",
        ):
            cur.execute("SELECT to_regclass(%s) AS relation", (f"public.{relation}",))
            row = cur.fetchone()
            if row is None or row["relation"] is None:
                raise HardFilterReviewStop(
                    "hard-filter review schema is missing; apply tracked migration "
                    "102_create_product_v1_hard_filter_operator_reviews.sql first"
                )


def load_current_rows(
    conn: psycopg.Connection[Any],
    silver_job_ids: Sequence[int],
) -> dict[int, Mapping[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                sj.id AS silver_job_id,
                sj.title,
                sj.company_name,
                sj.source_name,
                a.capability_fit_status,
                a.updated_at AS assessment_updated_at,
                h.employment_status,
                h.language_status,
                h.weekly_hours_status,
                h.seniority_status,
                h.salary_signal,
                h.deterministic_hard_filter_status,
                h.hard_filter_status,
                h.hard_filter_reasons,
                h.policy_version,
                h.operator_review_decision,
                h.operator_review_valid,
                review.decision AS active_review_decision,
                review.rationale AS active_review_rationale,
                review.assessment_updated_at AS active_review_assessment_updated_at,
                review.policy_version AS active_review_policy_version
            FROM silver_jobs sj
            JOIN job_product_assessments a
              ON a.silver_job_id = sj.id
            JOIN gold_product_v1_hard_filter_evaluation h
              ON h.silver_job_id = sj.id
            LEFT JOIN product_v1_hard_filter_reviews review
              ON review.silver_job_id = sj.id
             AND review.status = 'active'
            WHERE sj.id = ANY(%s)
            ORDER BY sj.id
            """,
            (list(silver_job_ids),),
        )
        return {int(row["silver_job_id"]): row for row in cur.fetchall()}


def _unknown_components(row: Mapping[str, Any]) -> tuple[str, ...]:
    components = (
        ("employment", row.get("employment_status")),
        ("languages", row.get("language_status")),
        ("weekly_hours", row.get("weekly_hours_status")),
        ("seniority_and_capability_fit", row.get("seniority_status")),
    )
    return tuple(
        name for name, status in components if status == "manual_review_required"
    )


def build_plan(
    *,
    reviews: Sequence[ReviewRequest],
    current_rows: Mapping[int, Mapping[str, Any]],
) -> dict[str, object]:
    proposals: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []

    for review in reviews:
        row = current_rows.get(review.silver_job_id)
        if row is None:
            blocked.append(
                {
                    "silver_job_id": review.silver_job_id,
                    "decision": review.decision,
                    "reason": "current_product_assessment_missing",
                }
            )
            continue

        deterministic_status = str(
            row.get("deterministic_hard_filter_status") or "unknown"
        )
        capability_fit = str(row.get("capability_fit_status") or "unknown")
        unknown_components = _unknown_components(row)

        if deterministic_status == "failed":
            blocked.append(
                {
                    "silver_job_id": review.silver_job_id,
                    "decision": review.decision,
                    "reason": "deterministic_hard_filter_failed_cannot_be_overridden",
                }
            )
            continue
        if deterministic_status != "unknown":
            blocked.append(
                {
                    "silver_job_id": review.silver_job_id,
                    "decision": review.decision,
                    "reason": "manual_review_not_required_for_current_assessment",
                }
            )
            continue
        if capability_fit != "passed":
            blocked.append(
                {
                    "silver_job_id": review.silver_job_id,
                    "decision": review.decision,
                    "reason": "approved_candidate_capability_fit_required_first",
                }
            )
            continue
        if not unknown_components:
            blocked.append(
                {
                    "silver_job_id": review.silver_job_id,
                    "decision": review.decision,
                    "reason": "no_unknown_source_evidence_component_to_review",
                }
            )
            continue

        assessment_updated_at = row.get("assessment_updated_at")
        policy_version = str(row.get("policy_version") or "")
        if assessment_updated_at is None or not policy_version:
            blocked.append(
                {
                    "silver_job_id": review.silver_job_id,
                    "decision": review.decision,
                    "reason": "assessment_or_policy_version_missing",
                }
            )
            continue

        existing_same = (
            row.get("active_review_decision") == review.decision
            and row.get("active_review_rationale") == review.rationale
            and row.get("active_review_assessment_updated_at") == assessment_updated_at
            and str(row.get("active_review_policy_version") or "") == policy_version
        )
        proposals.append(
            {
                "silver_job_id": review.silver_job_id,
                "title": row.get("title"),
                "company_name": row.get("company_name"),
                "source_name": row.get("source_name"),
                "decision": review.decision,
                "rationale": review.rationale,
                "reviewed_unknown_components": list(unknown_components),
                "assessment_updated_at": assessment_updated_at,
                "policy_version": policy_version,
                "already_current": existing_same,
            }
        )

    return {
        "schema": REPORT_SCHEMA,
        "mode": "plan",
        "request_count": len(reviews),
        "proposal_count": len(proposals),
        "blocked_count": len(blocked),
        "proposals": proposals,
        "blocked": blocked,
        "boundaries": {
            "database_reads": True,
            "database_writes": False,
            "deterministic_failed_override_allowed": False,
            "capability_fit_authority": False,
            "missing_source_facts_inferred": False,
            "ranking_or_top5_writes": False,
            "provider_or_llm_requests": 0,
            "application_or_submission_actions": False,
        },
    }


def apply_plan(
    conn: psycopg.Connection[Any],
    *,
    plan: Mapping[str, object],
    reviewed_by: str,
) -> tuple[int, int]:
    proposals = plan.get("proposals")
    if not isinstance(proposals, list):
        raise HardFilterReviewStop("review plan proposals are invalid")

    inserted = 0
    unchanged = 0
    with conn.cursor() as cur:
        for proposal in proposals:
            if not isinstance(proposal, Mapping):
                raise HardFilterReviewStop("review proposal is invalid")
            silver_job_id = int(proposal["silver_job_id"])
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"PRODUCT-V1-HARD-FILTER-REVIEW:{silver_job_id}",),
            )

            # Re-read the current version while locked. A stale plan may never write.
            cur.execute(
                """
                SELECT
                    a.capability_fit_status,
                    a.updated_at AS assessment_updated_at,
                    h.deterministic_hard_filter_status,
                    h.policy_version
                FROM job_product_assessments a
                JOIN gold_product_v1_hard_filter_evaluation h
                  ON h.silver_job_id = a.silver_job_id
                WHERE a.silver_job_id = %s
                """,
                (silver_job_id,),
            )
            current = cur.fetchone()
            if current is None:
                raise HardFilterReviewStop(
                    f"current assessment disappeared: {silver_job_id}"
                )
            if current["deterministic_hard_filter_status"] != "unknown":
                raise HardFilterReviewStop(
                    f"hard-filter review is no longer required: {silver_job_id}"
                )
            if current["capability_fit_status"] != "passed":
                raise HardFilterReviewStop(
                    f"capability fit is no longer passed: {silver_job_id}"
                )
            if current["assessment_updated_at"] != proposal["assessment_updated_at"]:
                raise HardFilterReviewStop(
                    f"assessment changed after plan: {silver_job_id}"
                )
            if current["policy_version"] != proposal["policy_version"]:
                raise HardFilterReviewStop(
                    f"hard-filter policy changed after plan: {silver_job_id}"
                )

            if proposal.get("already_current") is True:
                unchanged += 1
                continue

            cur.execute(
                """
                UPDATE product_v1_hard_filter_reviews
                SET status = 'superseded', updated_at = now()
                WHERE silver_job_id = %s
                  AND status = 'active'
                """,
                (silver_job_id,),
            )
            cur.execute(
                """
                INSERT INTO product_v1_hard_filter_reviews (
                    silver_job_id,
                    decision,
                    rationale,
                    reviewed_unknown_components,
                    assessment_updated_at,
                    policy_version,
                    review_scope,
                    status,
                    reviewed_by,
                    reviewed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', %s, now())
                """,
                (
                    silver_job_id,
                    proposal["decision"],
                    proposal["rationale"],
                    Jsonb(proposal["reviewed_unknown_components"]),
                    proposal["assessment_updated_at"],
                    proposal["policy_version"],
                    REVIEW_SCOPE,
                    reviewed_by,
                ),
            )
            inserted += 1

    conn.commit()
    return inserted, unchanged


def verify_applied(
    conn: psycopg.Connection[Any],
    proposals: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    results: list[dict[str, object]] = []
    with conn.cursor() as cur:
        for proposal in proposals:
            silver_job_id = int(proposal["silver_job_id"])
            cur.execute(
                """
                SELECT
                    deterministic_hard_filter_status,
                    hard_filter_status,
                    operator_review_decision,
                    operator_review_valid
                FROM gold_product_v1_hard_filter_evaluation
                WHERE silver_job_id = %s
                """,
                (silver_job_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise HardFilterReviewStop(
                    f"post-review hard-filter row missing: {silver_job_id}"
                )
            expected = str(proposal["decision"])
            if row["deterministic_hard_filter_status"] != "unknown":
                raise HardFilterReviewStop(
                    f"deterministic status changed unexpectedly: {silver_job_id}"
                )
            if row["operator_review_valid"] is not True:
                raise HardFilterReviewStop(
                    f"operator review not valid after apply: {silver_job_id}"
                )
            if row["operator_review_decision"] != expected:
                raise HardFilterReviewStop(
                    f"operator review decision mismatch: {silver_job_id}"
                )
            if row["hard_filter_status"] != expected:
                raise HardFilterReviewStop(
                    f"hard-filter status did not adopt review: {silver_job_id}"
                )
            results.append({"silver_job_id": silver_job_id, **dict(row)})
    conn.rollback()
    return tuple(results)


def write_report(report: Mapping[str, object], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(_json_safe(report), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan or apply version-bound Product V1 hard-filter operator reviews."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".runtime/demo/product_v1_hard_filter_review.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.input.is_file():
        raise SystemExit("hard-filter review input file does not exist")
    reviewed_by = args.reviewed_by.strip()
    if not reviewed_by:
        raise SystemExit("reviewed_by must not be blank")
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit("invalid hard-filter review approval token")

    decoded = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(decoded, Mapping):
        raise SystemExit("hard-filter review input root must be an object")
    reviews = parse_input(decoded)

    conn = connect()
    try:
        ensure_schema(conn)
        current_rows = load_current_rows(
            conn, [review.silver_job_id for review in reviews]
        )
        plan = build_plan(reviews=reviews, current_rows=current_rows)
        conn.rollback()

        inserted = 0
        unchanged = 0
        verification: tuple[dict[str, object], ...] = ()
        if args.apply:
            if int(plan["blocked_count"]) != 0:
                raise HardFilterReviewStop(
                    "hard-filter review apply refused because plan contains blockers"
                )
            inserted, unchanged = apply_plan(
                conn, plan=plan, reviewed_by=reviewed_by
            )
            verification = verify_applied(
                conn,
                [
                    proposal
                    for proposal in plan["proposals"]
                    if isinstance(proposal, Mapping)
                ],
            )

        report = {
            **plan,
            "mode": "apply" if args.apply else "plan",
            "inserted": inserted,
            "unchanged": unchanged,
            "verification": list(verification),
            "boundaries": {
                **dict(plan["boundaries"]),
                "database_writes": bool(args.apply and inserted),
            },
        }
        write_report(report, args.output)
    finally:
        conn.close()

    print("============================================")
    print("PRODUCT V1 HARD-FILTER OPERATOR REVIEW")
    print("============================================")
    print(f"MODE={report['mode']}")
    print(f"REQUESTS={report['request_count']}")
    print(f"PROPOSALS={report['proposal_count']}")
    print(f"BLOCKED={report['blocked_count']}")
    for proposal in report["proposals"]:
        print(
            "REVIEW="
            f"{proposal['silver_job_id']}|{proposal['decision']}|"
            f"unknown={','.join(proposal['reviewed_unknown_components'])}|"
            f"already_current={str(proposal['already_current']).lower()}|"
            f"{proposal['company_name']}|{proposal['title']}"
        )
    for item in report["blocked"]:
        print(
            "BLOCKED_JOB="
            f"{item['silver_job_id']}|{item['decision']}|{item['reason']}"
        )
    print(f"INSERTED={inserted}")
    print(f"UNCHANGED={unchanged}")
    for row in verification:
        print(
            "VERIFIED="
            f"{row['silver_job_id']}|deterministic={row['deterministic_hard_filter_status']}|"
            f"review={row['operator_review_decision']}|final={row['hard_filter_status']}"
        )
    print("DETERMINISTIC_FAILED_OVERRIDE_ALLOWED=false")
    print("CAPABILITY_FIT_AUTHORITY=false")
    print("MISSING_SOURCE_FACTS_INFERRED=false")
    print("PROVIDER_REQUESTS=0")
    print(f"artifact={args.output.resolve()}")
    print("PRODUCT_V1_HARD_FILTER_REVIEW=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
