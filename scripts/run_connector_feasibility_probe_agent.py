from __future__ import annotations

import argparse
import json
from typing import Sequence

import psycopg

from src.config import get_database_config
from src.search_intelligence.connector_feasibility import (
    OriginCandidate,
    build_connector_feasibility_review,
)

BOUNDARY = "no connector build, no connector registration, no source activation, no Bronze write, no scheduler change"


def connect() -> psycopg.Connection:
    return psycopg.connect(**get_database_config())


def load_candidates(conn: psycopg.Connection, *, company_key: str | None, include_missing_url: bool) -> list[OriginCandidate]:
    where = []
    params: list[object] = []
    if company_key:
        where.append("company_key = %s")
        params.append(company_key)
    elif not include_missing_url:
        where.append("candidate_url IS NOT NULL")

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    query = f"""
        SELECT
            id,
            company_key,
            company_name,
            candidate_url,
            source_name_candidate,
            status,
            risk_level
        FROM employer_origin_source_candidates
        {where_sql}
        ORDER BY company_key
    """
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [
        OriginCandidate(
            candidate_id=row[0],
            company_key=row[1],
            company_name=row[2],
            origin_url=row[3],
            source_name_candidate=row[4],
            status=row[5],
            risk_level=row[6],
        )
        for row in rows
    ]


def persist_review(conn: psycopg.Connection, review, *, scope: str) -> int:
    guardrails = {
        "connector_build_allowed": False,
        "connector_registration_allowed": False,
        "source_activation_allowed": False,
        "bronze_persistence_allowed": False,
        "scheduler_change_allowed": False,
        "bounded_http_probe_only": True,
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO connector_feasibility_reviews (
                scope,
                reviewed_by,
                candidate_count,
                likely_feasible_count,
                manual_review_count,
                blocked_count,
                missing_origin_url_count,
                fetch_enabled,
                guardrails
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                scope,
                review.reviewed_by,
                review.candidate_count,
                review.likely_feasible_count,
                review.manual_review_count,
                review.blocked_count,
                review.missing_origin_url_count,
                review.fetch_enabled,
                json.dumps(guardrails, sort_keys=True),
            ),
        )
        review_id = cur.fetchone()[0]
        for item in review.items:
            cur.execute(
                """
                INSERT INTO connector_feasibility_review_items (
                    review_id,
                    candidate_id,
                    company_key,
                    company_name,
                    origin_url,
                    source_name_candidate,
                    status,
                    risk_level,
                    http_status,
                    reachable,
                    page_type,
                    sample_job_count,
                    sample_job_urls,
                    feasibility_status,
                    decision,
                    blocker_code,
                    reason,
                    recommended_next_action,
                    evidence,
                    url_quality_status,
                    url_quality_feedback_code,
                    url_repair_candidate_url,
                    structural_job_evidence_count,
                    job_search_page_evidence_count,
                    job_detail_candidate_evidence_count,
                    career_context_evidence_count,
                    rejected_noise_count,
                    evidence_classification
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    review_id,
                    item.candidate.candidate_id,
                    item.candidate.company_key,
                    item.candidate.company_name,
                    item.candidate.origin_url,
                    item.candidate.source_name_candidate,
                    item.candidate.status,
                    item.candidate.risk_level,
                    item.http_status,
                    item.reachable,
                    item.page_type,
                    item.sample_job_count,
                    json.dumps(list(item.sample_job_urls), sort_keys=True),
                    item.feasibility_status,
                    item.decision,
                    item.blocker_code,
                    item.reason,
                    item.recommended_next_action,
                    json.dumps(item.evidence, sort_keys=True),
                    item.url_quality.status,
                    item.url_quality.code,
                    item.url_quality.repair_candidate_url,
                    item.structural_job_evidence_count,
                    item.job_search_page_evidence_count,
                    item.job_detail_candidate_evidence_count,
                    item.career_context_evidence_count,
                    item.rejected_noise_count,
                    json.dumps(item.evidence_classification.as_dict(), sort_keys=True),
                ),
            )
    conn.commit()
    return int(review_id)


def print_review(review, *, persisted_review_id: int | None) -> None:
    print("S7N Connector Feasibility + Sample Job Probe")
    print(f"boundary: {BOUNDARY}")
    print("---")
    print(f"candidate_count: {review.candidate_count}")
    print(f"likely_feasible_count: {review.likely_feasible_count}")
    print(f"manual_review_count: {review.manual_review_count}")
    print(f"blocked_count: {review.blocked_count}")
    print(f"missing_origin_url_count: {review.missing_origin_url_count}")
    print(f"fetch_enabled: {review.fetch_enabled}")
    print(f"persisted_review_id: {persisted_review_id or '-'}")
    print("---")
    for item in review.items:
        status = item.http_status if item.http_status is not None else "-"
        print(
            f"- {item.candidate.company_name} [{item.candidate.company_key}] | "
            f"feasibility={item.feasibility_status} | decision={item.decision} | "
            f"http={status} | structural={item.structural_job_evidence_count} | "
            f"job_search={item.job_search_page_evidence_count} | job_detail={item.job_detail_candidate_evidence_count} | "
            f"career_context={item.career_context_evidence_count} | rejected_noise={item.rejected_noise_count} | "
            f"blocker={item.blocker_code or 'none'}"
        )
        print(f"  url: {item.candidate.origin_url or '-'}")
        print(f"  url_quality: {item.url_quality.status} | code={item.url_quality.code or '-'}")
        if item.url_quality.repair_candidate_url:
            print(f"  repair_candidate: {item.url_quality.repair_candidate_url}")
        print(f"  reason: {item.reason}")
        print(f"  next: {item.recommended_next_action}")
        for sample in item.sample_job_urls[:3]:
            print(f"  sample: {sample}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded connector feasibility and sample job probe.")
    parser.add_argument("--company-key", help="Run probe for one company key.")
    parser.add_argument("--include-missing-url", action="store_true", help="Include candidates without candidate_url.")
    parser.add_argument("--reviewed-by", default="system")
    parser.add_argument("--no-fetch", action="store_true", help="Disable HTTP fetch and only evaluate URL shape.")
    parser.add_argument("--write", action="store_true", help="Persist review result.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    with connect() as conn:
        candidates = load_candidates(
            conn,
            company_key=args.company_key,
            include_missing_url=args.include_missing_url,
        )
        review = build_connector_feasibility_review(
            candidates,
            reviewed_by=args.reviewed_by,
            fetch_enabled=not args.no_fetch,
        )
        persisted_review_id = None
        if args.write:
            scope = args.company_key or ("all_candidates" if args.include_missing_url else "selected_origin_candidates")
            persisted_review_id = persist_review(conn, review, scope=scope)
    print_review(review, persisted_review_id=persisted_review_id)
    if not args.write:
        print("NEXT: review the bounded probe result, then rerun with --write if the review should be persisted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
