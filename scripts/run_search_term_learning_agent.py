"""S5B search-term learning and reassessment queue agent.

Reads false-negative risk assessments and converts them into reviewable search-term
suggestions plus reassessment work items. This is intentionally review-first: it never
mutates active search profiles, registers connectors, activates sources or changes schedulers.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.search_intelligence.false_negative_risk import FalseNegativeRiskAssessment
from src.search_intelligence.search_term_learning import (
    ReassessmentQueueItem,
    SearchTermSuggestion,
    build_reassessment_queue_items,
    build_search_term_suggestions,
)


class DatabaseConfig:
    @classmethod
    def dsn(cls) -> str:
        return (
            f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
            f"port={os.environ.get('POSTGRES_PORT', '5432')} "
            f"dbname={os.environ['POSTGRES_DB']} "
            f"user={os.environ['POSTGRES_USER']} "
            f"password={os.environ['POSTGRES_PASSWORD']}"
        )


def _tuple_from_json_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return ()


def load_latest_false_negative_assessments(
    conn: psycopg.Connection[Any],
) -> list[FalseNegativeRiskAssessment]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select distinct on (s.candidate_id)
                s.candidate_id,
                s.company_key,
                coalesce(c.company_name, s.evidence ->> 'company_name', s.company_key) as company_name,
                s.risk_level,
                s.sighting_count,
                s.recent_sighting_count,
                s.last_observed_at::text as last_observed_at,
                s.reason,
                s.suggested_search_terms,
                s.evidence
            from false_negative_risk_snapshots s
            left join employer_origin_source_candidates c on c.id = s.candidate_id
            order by s.candidate_id, s.created_at desc
            """
        )
        rows = cur.fetchall()

    assessments: list[FalseNegativeRiskAssessment] = []
    for row in rows:
        evidence = dict(row["evidence"] or {})
        assessments.append(
            FalseNegativeRiskAssessment(
                candidate_id=int(row["candidate_id"]),
                company_key=str(row["company_key"]),
                company_name=str(row["company_name"]),
                risk_level=str(row["risk_level"]),
                sighting_count=int(row["sighting_count"] or 0),
                recent_sighting_count=int(row["recent_sighting_count"] or 0),
                last_observed_at=row["last_observed_at"],
                reason=str(row["reason"]),
                suggested_search_terms=tuple(row["suggested_search_terms"] or ()),
                evidence_sources=_tuple_from_json_list(evidence.get("evidence_sources")),
                evidence_titles=_tuple_from_json_list(evidence.get("evidence_titles")),
            )
        )
    return assessments


def write_search_term_suggestions(
    conn: psycopg.Connection[Any],
    *,
    suggestions: list[SearchTermSuggestion],
    reviewed_by: str,
) -> int:
    count = 0
    with conn.cursor() as cur:
        for suggestion in suggestions:
            cur.execute(
                """
                insert into search_term_suggestions (
                    candidate_id,
                    company_key,
                    source_name_candidate,
                    source_family_candidate,
                    suggested_term,
                    risk_level,
                    evidence_count,
                    last_observed_at,
                    reason,
                    evidence,
                    reviewed_by
                )
                select
                    c.id,
                    c.company_key,
                    c.source_name_candidate,
                    c.source_family_candidate,
                    %s,
                    %s,
                    %s,
                    %s::timestamptz,
                    %s,
                    %s::jsonb,
                    %s
                from employer_origin_source_candidates c
                where c.id = %s
                on conflict (candidate_id, suggested_term)
                do update set
                    risk_level = excluded.risk_level,
                    evidence_count = excluded.evidence_count,
                    last_observed_at = excluded.last_observed_at,
                    reason = excluded.reason,
                    evidence = excluded.evidence,
                    reviewed_by = excluded.reviewed_by,
                    status = 'proposed',
                    updated_at = now()
                """,
                (
                    suggestion.suggested_term,
                    suggestion.risk_level,
                    suggestion.evidence_count,
                    suggestion.last_observed_at,
                    suggestion.reason,
                    json.dumps(asdict(suggestion), ensure_ascii=False),
                    reviewed_by,
                    suggestion.candidate_id,
                ),
            )
            count += 1
    return count


def write_reassessment_queue(
    conn: psycopg.Connection[Any],
    *,
    items: list[ReassessmentQueueItem],
    reviewed_by: str,
) -> int:
    count = 0
    with conn.cursor() as cur:
        for item in items:
            cur.execute(
                """
                insert into candidate_reassessment_queue (
                    candidate_id,
                    company_key,
                    risk_level,
                    priority,
                    trigger_reason,
                    suggested_search_terms,
                    evidence,
                    reviewed_by
                ) values (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                on conflict (candidate_id) where status = 'open'
                do update set
                    risk_level = excluded.risk_level,
                    priority = excluded.priority,
                    trigger_reason = excluded.trigger_reason,
                    suggested_search_terms = excluded.suggested_search_terms,
                    evidence = excluded.evidence,
                    reviewed_by = excluded.reviewed_by,
                    updated_at = now()
                """,
                (
                    item.candidate_id,
                    item.company_key,
                    item.risk_level,
                    item.priority,
                    item.trigger_reason,
                    list(item.suggested_search_terms),
                    json.dumps(asdict(item), ensure_ascii=False),
                    reviewed_by,
                ),
            )
            count += 1
    return count


def run(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.dsn()) as conn:
        assessments = load_latest_false_negative_assessments(conn)
        suggestions = build_search_term_suggestions(assessments)
        reassessment_items = build_reassessment_queue_items(assessments)

        print("Search Term Learning Preview")
        print(f"assessment_count: {len(assessments)}")
        print(f"suggested_term_count: {len(suggestions)}")
        print(f"reassessment_item_count: {len(reassessment_items)}")

        for item in reassessment_items[: args.limit]:
            terms = ", ".join(item.suggested_search_terms) if item.suggested_search_terms else "-"
            print("---")
            print(f"company: {item.company_name}")
            print(f"company_key: {item.company_key}")
            print(f"risk_level: {item.risk_level}")
            print(f"priority: {item.priority}")
            print(f"suggested_terms: {terms}")
            print(f"reason: {item.trigger_reason}")

        if args.write:
            suggestion_count = write_search_term_suggestions(
                conn,
                suggestions=suggestions,
                reviewed_by=args.reviewed_by,
            )
            reassessment_count = write_reassessment_queue(
                conn,
                items=reassessment_items,
                reviewed_by=args.reviewed_by,
            )
            conn.commit()
            print("---")
            print("write_mode: true")
            print(f"search_term_suggestion_upsert_count: {suggestion_count}")
            print(f"reassessment_queue_upsert_count: {reassessment_count}")
        else:
            print("---")
            print("write_mode: false")
            print("NEXT: rerun with --write after reviewing the preview.")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create reviewable search-term suggestions and reassessment queue items from false-negative risk.")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--reviewed-by", default="agent")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
