from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.config import get_database_config


INPUT_SCHEMA = "job_application_pipeline.product_v1_capability_fit_review_input.v1"
REPORT_SCHEMA = "job_application_pipeline.product_v1_capability_fit_review.v1"
APPROVAL_TOKEN = "PRODUCT-V1-CAPABILITY-FIT-REVIEW-001"
LOCK_KEY = "DEMO-001:product_v1_capability_fit_review"
CAPABILITY_EVIDENCE_CLASSES = frozenset(
    {
        "professional_employment",
        "formal_education",
        "portfolio_implementation",
        "training_certification",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class CapabilityFitReviewStop(RuntimeError):
    """Fail closed when current evidence cannot authorize a capability-fit review."""


@dataclass(frozen=True)
class ReviewRequest:
    silver_job_id: int
    decision: str
    rationale: str
    candidate_fact_keys: tuple[str, ...]


@dataclass(frozen=True)
class CandidateProfileBinding:
    profile_version: str
    payload_sha256: str


@dataclass(frozen=True)
class ReviewPlanItem:
    silver_job_id: int
    decision: str
    referenced_fact_count: int
    assessment_updated_at: str
    assessment_detail_sha256: str
    current_capability_fit_status: str
    current_product_readiness_status: str
    would_change: bool


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


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CapabilityFitReviewStop(message)


def parse_input(payload: Mapping[str, object]) -> tuple[str, tuple[ReviewRequest, ...]]:
    _require(payload.get("schema") == INPUT_SCHEMA, "capability-fit review input schema is invalid")
    expected_profile_sha256 = str(payload.get("candidate_profile_sha256") or "").strip()
    _require(
        _SHA256_RE.fullmatch(expected_profile_sha256) is not None,
        "candidate_profile_sha256 must be a lowercase SHA-256",
    )
    raw_reviews = payload.get("reviews")
    _require(isinstance(raw_reviews, list) and bool(raw_reviews), "capability-fit input requires reviews")

    reviews: list[ReviewRequest] = []
    seen_jobs: set[int] = set()
    for raw in raw_reviews:
        _require(isinstance(raw, Mapping), "capability-fit review item must be an object")
        try:
            silver_job_id = int(raw.get("silver_job_id") or 0)
        except (TypeError, ValueError) as exc:
            raise CapabilityFitReviewStop("silver_job_id must be an integer") from exc
        _require(silver_job_id > 0, "silver_job_id must be positive")
        _require(silver_job_id not in seen_jobs, f"duplicate silver_job_id: {silver_job_id}")
        seen_jobs.add(silver_job_id)

        decision = str(raw.get("decision") or "").strip().lower()
        _require(decision in {"passed", "failed"}, "capability-fit decision must be passed or failed")
        rationale = " ".join(str(raw.get("rationale") or "").split())
        _require(len(rationale) >= 8, f"capability-fit rationale is too short: {silver_job_id}")

        raw_keys = raw.get("candidate_fact_keys")
        _require(isinstance(raw_keys, list), "candidate_fact_keys must be an array")
        keys = tuple(sorted({str(value).strip() for value in raw_keys if str(value).strip()}))
        _require(len(keys) == len(raw_keys), "candidate_fact_keys must be nonblank and unique")
        if decision == "passed":
            _require(bool(keys), "passed capability fit requires approved Candidate Fact references")
        reviews.append(
            ReviewRequest(
                silver_job_id=silver_job_id,
                decision=decision,
                rationale=rationale,
                candidate_fact_keys=keys,
            )
        )
    return expected_profile_sha256, tuple(reviews)


def ensure_schema(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        for relation in (
            "product_v1_capability_fit_reviews",
            "candidate_fact_profiles",
            "candidate_facts",
            "job_product_assessments",
            "gold_product_v1_job_readiness",
        ):
            cur.execute("SELECT to_regclass(%s) AS relation", (f"public.{relation}",))
            row = cur.fetchone()
            _require(row is not None and row["relation"] is not None, f"missing relation: {relation}")


def load_profile(conn: psycopg.Connection[Any]) -> CandidateProfileBinding:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT profile_version, payload_sha256, status
            FROM candidate_fact_profiles
            WHERE profile_key = 'default'
            """
        )
        row = cur.fetchone()
    _require(row is not None, "approved default Candidate Fact profile is missing")
    _require(str(row["status"]) == "approved", "default Candidate Fact profile is not approved")
    profile_version = str(row["profile_version"] or "").strip()
    payload_sha256 = str(row["payload_sha256"] or "").strip()
    _require(bool(profile_version), "Candidate Fact profile version is missing")
    _require(_SHA256_RE.fullmatch(payload_sha256) is not None, "Candidate Fact profile hash is invalid")
    return CandidateProfileBinding(profile_version=profile_version, payload_sha256=payload_sha256)


def load_approved_capability_facts(
    conn: psycopg.Connection[Any],
    fact_keys: Sequence[str],
) -> dict[str, Mapping[str, Any]]:
    if not fact_keys:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT fact_key, evidence_class, approval_status, valid_from, valid_until
            FROM candidate_facts
            WHERE profile_key = 'default'
              AND fact_key = ANY(%s)
            """,
            (list(fact_keys),),
        )
        rows = tuple(cur.fetchall())
    return {str(row["fact_key"]): row for row in rows}


def load_job_rows(
    conn: psycopg.Connection[Any],
    silver_job_ids: Sequence[int],
    *,
    for_update: bool = False,
) -> dict[int, Mapping[str, Any]]:
    lock_clause = "FOR UPDATE OF a" if for_update else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                a.silver_job_id,
                a.origin_validation_status,
                a.activity_status,
                a.capability_fit_status,
                a.updated_at AS assessment_updated_at,
                a.ranking_factors,
                r.product_readiness_status,
                review.decision AS active_review_decision,
                review.rationale AS active_review_rationale,
                review.candidate_profile_sha256 AS active_review_profile_sha256,
                review.assessment_detail_sha256 AS active_review_detail_sha256,
                review.assessment_updated_at AS active_review_assessment_updated_at,
                review.referenced_fact_keys AS active_review_fact_keys
            FROM job_product_assessments a
            JOIN gold_product_v1_job_readiness r
              ON r.silver_job_id = a.silver_job_id
            LEFT JOIN product_v1_capability_fit_reviews review
              ON review.silver_job_id = a.silver_job_id
             AND review.status = 'active'
            WHERE a.silver_job_id = ANY(%s)
            {lock_clause}
            """,
            (list(silver_job_ids),),
        )
        rows = tuple(cur.fetchall())
    return {int(row["silver_job_id"]): row for row in rows}


def _detail_sha(row: Mapping[str, Any]) -> str:
    ranking_factors = row.get("ranking_factors")
    _require(isinstance(ranking_factors, Mapping), "assessment ranking_factors are missing")
    value = str(ranking_factors.get("detail_description_sha256") or "").strip()
    _require(_SHA256_RE.fullmatch(value) is not None, "assessment detail fingerprint is missing")
    return value


def validate_review_authority(
    *,
    review: ReviewRequest,
    profile: CandidateProfileBinding,
    expected_profile_sha256: str,
    fact_rows: Mapping[str, Mapping[str, Any]],
    job_row: Mapping[str, Any],
    today: date,
) -> ReviewPlanItem:
    _require(profile.payload_sha256 == expected_profile_sha256, "Candidate Fact profile changed since operator review")
    _require(str(job_row.get("origin_validation_status") or "") == "validated", "job origin is not validated")
    _require(str(job_row.get("activity_status") or "") == "active", "job is not currently active")

    for fact_key in review.candidate_fact_keys:
        fact = fact_rows.get(fact_key)
        _require(fact is not None, f"Candidate Fact is missing: {fact_key}")
        _require(str(fact.get("approval_status") or "") == "approved", f"Candidate Fact is not approved: {fact_key}")
        _require(
            str(fact.get("evidence_class") or "") in CAPABILITY_EVIDENCE_CLASSES,
            f"Candidate Fact is not capability evidence: {fact_key}",
        )
        valid_from = fact.get("valid_from")
        valid_until = fact.get("valid_until")
        if isinstance(valid_from, date):
            _require(valid_from <= today, f"Candidate Fact is not yet valid: {fact_key}")
        if isinstance(valid_until, date):
            _require(valid_until >= today, f"Candidate Fact is expired: {fact_key}")

    detail_sha256 = _detail_sha(job_row)
    assessment_updated_at = job_row.get("assessment_updated_at")
    _require(isinstance(assessment_updated_at, datetime), "assessment version timestamp is missing")
    current_status = str(job_row.get("capability_fit_status") or "unknown")
    readiness = str(job_row.get("product_readiness_status") or "")

    active_keys_raw = job_row.get("active_review_fact_keys")
    active_keys = tuple(sorted(str(value) for value in active_keys_raw)) if isinstance(active_keys_raw, list) else ()
    unchanged = (
        str(job_row.get("active_review_decision") or "") == review.decision
        and str(job_row.get("active_review_rationale") or "") == review.rationale
        and str(job_row.get("active_review_profile_sha256") or "") == profile.payload_sha256
        and str(job_row.get("active_review_detail_sha256") or "") == detail_sha256
        and job_row.get("active_review_assessment_updated_at") == assessment_updated_at
        and active_keys == review.candidate_fact_keys
        and current_status == review.decision
    )
    return ReviewPlanItem(
        silver_job_id=review.silver_job_id,
        decision=review.decision,
        referenced_fact_count=len(review.candidate_fact_keys),
        assessment_updated_at=assessment_updated_at.isoformat(),
        assessment_detail_sha256=detail_sha256,
        current_capability_fit_status=current_status,
        current_product_readiness_status=readiness,
        would_change=not unchanged,
    )


def build_plan(
    conn: psycopg.Connection[Any],
    *,
    expected_profile_sha256: str,
    reviews: Sequence[ReviewRequest],
) -> tuple[CandidateProfileBinding, tuple[ReviewPlanItem, ...]]:
    profile = load_profile(conn)
    all_keys = sorted({key for review in reviews for key in review.candidate_fact_keys})
    facts = load_approved_capability_facts(conn, all_keys)
    jobs = load_job_rows(conn, [review.silver_job_id for review in reviews])
    _require(len(jobs) == len(reviews), "one or more Product V1 assessment rows are missing")
    today = date.today()
    plan = tuple(
        validate_review_authority(
            review=review,
            profile=profile,
            expected_profile_sha256=expected_profile_sha256,
            fact_rows=facts,
            job_row=jobs[review.silver_job_id],
            today=today,
        )
        for review in reviews
    )
    return profile, plan


def apply_reviews(
    conn: psycopg.Connection[Any],
    *,
    expected_profile_sha256: str,
    reviews: Sequence[ReviewRequest],
    reviewed_by: str,
) -> tuple[int, int]:
    changed = 0
    unchanged = 0
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (LOCK_KEY,))

    profile = load_profile(conn)
    _require(profile.payload_sha256 == expected_profile_sha256, "Candidate Fact profile changed before Apply")
    all_keys = sorted({key for review in reviews for key in review.candidate_fact_keys})
    facts = load_approved_capability_facts(conn, all_keys)
    jobs = load_job_rows(conn, [review.silver_job_id for review in reviews], for_update=True)
    _require(len(jobs) == len(reviews), "one or more Product V1 assessment rows are missing before Apply")

    for review in reviews:
        job = jobs[review.silver_job_id]
        plan = validate_review_authority(
            review=review,
            profile=profile,
            expected_profile_sha256=expected_profile_sha256,
            fact_rows=facts,
            job_row=job,
            today=date.today(),
        )
        if not plan.would_change:
            unchanged += 1
            continue

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE product_v1_capability_fit_reviews
                SET status = 'superseded', updated_at = now()
                WHERE silver_job_id = %s
                  AND status = 'active'
                """,
                (review.silver_job_id,),
            )
            cur.execute(
                """
                UPDATE job_product_assessments
                SET capability_fit_status = %s,
                    updated_at = now()
                WHERE silver_job_id = %s
                RETURNING updated_at
                """,
                (review.decision, review.silver_job_id),
            )
            updated = cur.fetchone()
            _require(updated is not None, "assessment update disappeared during Apply")
            assessment_updated_at = updated["updated_at"]
            cur.execute(
                """
                INSERT INTO product_v1_capability_fit_reviews (
                    silver_job_id,
                    decision,
                    rationale,
                    candidate_profile_version,
                    candidate_profile_sha256,
                    assessment_detail_sha256,
                    assessment_updated_at,
                    referenced_fact_keys,
                    status,
                    reviewed_by,
                    reviewed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, now())
                """,
                (
                    review.silver_job_id,
                    review.decision,
                    review.rationale,
                    profile.profile_version,
                    profile.payload_sha256,
                    plan.assessment_detail_sha256,
                    assessment_updated_at,
                    Jsonb(list(review.candidate_fact_keys)),
                    reviewed_by,
                ),
            )
        changed += 1

    conn.commit()
    return changed, unchanged


def load_post_apply_statuses(
    conn: psycopg.Connection[Any], silver_job_ids: Sequence[int]
) -> list[dict[str, object]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                r.silver_job_id,
                r.product_readiness_status,
                r.hard_filter_status,
                a.capability_fit_status
            FROM gold_product_v1_job_readiness r
            JOIN job_product_assessments a
              ON a.silver_job_id = r.silver_job_id
            WHERE r.silver_job_id = ANY(%s)
            ORDER BY r.silver_job_id
            """,
            (list(silver_job_ids),),
        )
        return [dict(row) for row in cur.fetchall()]


def write_report(payload: Mapping[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan or apply evidence-bound Product V1 Candidate Fact capability-fit reviews.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(".runtime/demo/product_v1_capability_fit_review.json"))
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    _require(args.input.is_file(), "capability-fit review input file does not exist")
    reviewed_by = args.reviewed_by.strip()
    _require(bool(reviewed_by), "reviewed_by must not be blank")
    if args.apply:
        _require(args.approval_token == APPROVAL_TOKEN, "invalid capability-fit review approval token")

    raw = json.loads(args.input.read_text(encoding="utf-8"))
    _require(isinstance(raw, Mapping), "capability-fit review input root must be an object")
    expected_profile_sha256, reviews = parse_input(raw)

    conn = connect()
    try:
        ensure_schema(conn)
        profile, plan = build_plan(
            conn,
            expected_profile_sha256=expected_profile_sha256,
            reviews=reviews,
        )
        conn.rollback()
        changed = 0
        unchanged = 0
        if args.apply:
            changed, unchanged = apply_reviews(
                conn,
                expected_profile_sha256=expected_profile_sha256,
                reviews=reviews,
                reviewed_by=reviewed_by,
            )
        post = load_post_apply_statuses(conn, [review.silver_job_id for review in reviews]) if args.apply else []
        conn.rollback()
    finally:
        conn.close()

    report = {
        "schema": REPORT_SCHEMA,
        "mode": "apply" if args.apply else "plan",
        "candidate_profile": {
            "profile_version": profile.profile_version,
            "payload_sha256": profile.payload_sha256,
        },
        "reviews": [_json_safe(item.__dict__) for item in plan],
        "would_change_count": sum(1 for item in plan if item.would_change),
        "changed_count": changed,
        "unchanged_count": unchanged,
        "post_apply": post,
        "boundaries": {
            "candidate_fact_statements_emitted": False,
            "candidate_fact_provenance_emitted": False,
            "candidate_fact_mutation": False,
            "capability_fit_status_only_assessment_mutation": bool(args.apply and changed),
            "deterministic_hard_filter_override": False,
            "ranking_or_top5_authority": False,
            "provider_or_llm_requests": 0,
            "network_requests": 0,
            "application_or_submission_actions": False,
        },
    }
    write_report(report, args.output)

    print("============================================")
    print("PRODUCT V1 CAPABILITY FIT REVIEW")
    print("============================================")
    print(f"MODE={report['mode']}")
    print(f"PROFILE_SHA256={profile.payload_sha256}")
    print(f"REVIEW_COUNT={len(plan)}")
    print(f"WOULD_CHANGE={report['would_change_count']}")
    print(f"CHANGED={changed}")
    print(f"UNCHANGED={unchanged}")
    print("CANDIDATE_FACT_STATEMENTS_EMITTED=false")
    print("DETERMINISTIC_HARD_FILTER_OVERRIDE=false")
    print("PROVIDER_REQUESTS=0")
    print(f"artifact={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
