"""Run S7I Candidate Expansion from Market Observations.

Boundary: review/audit only. This script reads unregistered market observations
and existing employer-origin candidates, then creates a candidate-expansion
review. It does not create employer-origin candidates, browse external pages,
register connectors, activate sources, write Bronze records or modify schedules.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.candidate_expansion import (
    CandidateExpansionItem,
    CandidateExpansionReview,
    KnownCandidate,
    MarketCompanyObservation,
    build_candidate_expansion_review,
)


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _tuple_from_pg_array(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(str(item) for item in value if item)
    if isinstance(value, tuple):
        return tuple(str(item) for item in value if item)
    return (str(value),)


def load_unregistered_company_observations(
    conn: psycopg.Connection[Any],
    *,
    source_name: str | None,
    days: int,
    limit_companies: int,
) -> list[MarketCompanyObservation]:
    clauses = [
        "item_type = 'company'",
        "novelty_state = 'unregistered_company'",
        "created_at >= now() - (%s || ' days')::interval",
        "company_key is not null",
        "company_name is not null",
    ]
    params: list[Any] = [days]
    if source_name:
        clauses.append("source_name = %s")
        params.append(source_name)
    params.append(limit_companies)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            select
                company_key,
                company_name,
                source_name,
                count(*)::int as observation_count,
                max(observed_at)::text as latest_observed_at,
                array_agg(distinct search_term) filter (where search_term is not null) as search_terms,
                array_agg(distinct title) filter (where title is not null) as sample_titles
            from aggregator_novelty_items
            where {' and '.join(clauses)}
            group by company_key, company_name, source_name
            order by observation_count desc, latest_observed_at desc nulls last, company_name
            limit %s
            """,
            params,
        )
        rows = cur.fetchall()

    return [
        MarketCompanyObservation(
            company_key=str(row["company_key"]),
            company_name=str(row["company_name"]),
            source_name=str(row["source_name"]),
            observation_count=int(row["observation_count"]),
            latest_observed_at=row["latest_observed_at"],
            search_terms=_tuple_from_pg_array(row["search_terms"]),
            sample_titles=_tuple_from_pg_array(row["sample_titles"]),
        )
        for row in rows
    ]


def load_known_candidates(conn: psycopg.Connection[Any]) -> list[KnownCandidate]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select
                id,
                company_key,
                company_name,
                status,
                source_family_candidate
            from employer_origin_source_candidates
            order by company_key, id
            """
        )
        rows = cur.fetchall()

    return [
        KnownCandidate(
            candidate_id=int(row["id"]),
            company_key=str(row["company_key"]),
            company_name=str(row["company_name"]),
            status=str(row["status"]),
            source_family_candidate=row["source_family_candidate"],
        )
        for row in rows
    ]


def write_review(
    conn: psycopg.Connection[Any],
    *,
    review: CandidateExpansionReview,
    reviewed_by: str,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into candidate_expansion_reviews (
                source_name,
                observed_since,
                observed_until,
                reviewed_by,
                total_observation_count,
                company_count,
                create_recommended_count,
                manual_review_count,
                insufficient_evidence_count,
                already_known_count,
                suppressed_count,
                boundary
            ) values (
                %s, %s::timestamptz, %s::timestamptz, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
            )
            returning id
            """,
            (
                review.source_name,
                review.observed_since,
                review.observed_until,
                reviewed_by,
                review.total_observation_count,
                review.company_count,
                review.create_recommended_count,
                review.manual_review_count,
                review.insufficient_evidence_count,
                review.already_known_count,
                review.suppressed_count,
                json.dumps(review.boundary, sort_keys=True),
            ),
        )
        review_id = int(cur.fetchone()["id"])
        for item in review.items:
            cur.execute(
                """
                insert into candidate_expansion_review_items (
                    review_id,
                    company_key,
                    company_name,
                    source_name,
                    decision,
                    priority,
                    evidence_count,
                    distinct_search_term_count,
                    sample_title_count,
                    latest_observed_at,
                    known_candidate_id,
                    known_candidate_status,
                    recommended_next_action,
                    reason,
                    evidence
                ) values (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::timestamptz, %s, %s, %s, %s, %s::jsonb
                )
                """,
                (
                    review_id,
                    item.company_key,
                    item.company_name,
                    item.source_name,
                    item.decision,
                    item.priority,
                    item.evidence_count,
                    item.distinct_search_term_count,
                    item.sample_title_count,
                    item.latest_observed_at,
                    item.known_candidate_id,
                    item.known_candidate_status,
                    item.recommended_next_action,
                    item.reason,
                    json.dumps(item.evidence, sort_keys=True),
                ),
            )
    conn.commit()
    return review_id


def _print_item(item: CandidateExpansionItem) -> None:
    titles = item.evidence.get("sample_titles", []) if isinstance(item.evidence, dict) else []
    title_preview = "; ".join(str(title) for title in list(titles)[:3])
    print(
        f"- {item.company_key} | {item.company_name} | decision={item.decision} | "
        f"priority={item.priority} | evidence={item.evidence_count} | terms={item.distinct_search_term_count}"
    )
    print(f"  next: {item.recommended_next_action}")
    print(f"  reason: {item.reason}")
    if title_preview:
        print(f"  samples: {title_preview}")


def print_review(review: CandidateExpansionReview, *, persisted_review_id: int | None) -> None:
    print("S7I Candidate Expansion from Market Observations")
    print("boundary: no browsing, no candidate creation, no connector registration, no source activation, no Bronze write, no scheduler change")
    print("---")
    print(f"source_name: {review.source_name or 'all'}")
    print(f"company_count: {review.company_count}")
    print(f"total_observation_count: {review.total_observation_count}")
    print(f"create_recommended_count: {review.create_recommended_count}")
    print(f"manual_review_count: {review.manual_review_count}")
    print(f"already_known_count: {review.already_known_count}")
    print(f"insufficient_evidence_count: {review.insufficient_evidence_count}")
    print(f"suppressed_count: {review.suppressed_count}")
    print(f"persisted_review_id: {persisted_review_id if persisted_review_id is not None else '-'}")
    print("---")

    for heading, decisions in (
        ("create_candidate_recommended", {"create_candidate_recommended"}),
        ("manual_review_required", {"manual_review_required"}),
        ("already_known / active_monitoring", {"already_known", "active_candidate_monitoring"}),
        ("insufficient_or_suppressed", {"insufficient_evidence", "suppress_as_noise"}),
    ):
        rows = [item for item in review.items if item.decision in decisions][:10]
        print(heading)
        if not rows:
            print("- none")
        for item in rows:
            _print_item(item)
        print("---")

    if persisted_review_id is None:
        print("NEXT: review the candidate expansion output, then rerun with --write to persist the review.")
    else:
        print("NEXT: use the persisted review to decide which recommendations may become employer-origin candidates in a later gated block.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-name", default=None, help="Optional source filter, e.g. stepstone")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--limit-companies", type=int, default=50)
    parser.add_argument("--min-create-observations", type=int, default=4)
    parser.add_argument("--min-review-observations", type=int, default=2)
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--write", action="store_true", help="Persist review state only; does not create candidates")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with connect() as conn:
        observations = load_unregistered_company_observations(
            conn,
            source_name=args.source_name,
            days=args.days,
            limit_companies=args.limit_companies,
        )
        known_candidates = load_known_candidates(conn)
        review = build_candidate_expansion_review(
            observations,
            known_candidates,
            source_name=args.source_name,
            min_create_observations=args.min_create_observations,
            min_review_observations=args.min_review_observations,
        )
        persisted_review_id = write_review(conn, review=review, reviewed_by=args.reviewed_by) if args.write else None
    print_review(review, persisted_review_id=persisted_review_id)


if __name__ == "__main__":
    main()
