"""Run the S6B bounded aggregator novelty loop assessment."""
from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.search_intelligence.aggregator_novelty import (
    CYCLE_SCOPE,
    AggregatorEvidenceRow,
    AggregatorNoveltyItem,
    AggregatorNoveltySnapshot,
    KnownCompanyCandidate,
    PreviousNoveltySnapshot,
    build_aggregator_novelty_snapshot,
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


def load_market_evidence(
    conn: psycopg.Connection[Any],
    *,
    source_name: str,
    search_profile_name: str | None,
    search_term: str | None,
    days: int,
    limit: int,
) -> list[AggregatorEvidenceRow]:
    clauses = ["source_name = %s", "observed_at >= now() - (%s || ' days')::interval"]
    params: list[Any] = [source_name, days]
    if search_profile_name:
        clauses.append("search_profile_name = %s")
        params.append(search_profile_name)
    if search_term:
        clauses.append("search_term = %s")
        params.append(search_term)
    params.append(limit)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            select
                id,
                source_name,
                normalized_company_key,
                company_name,
                title,
                search_profile_name,
                search_term,
                evidence_url,
                observed_at::text as observed_at
            from market_evidence
            where {' and '.join(clauses)}
            order by observed_at desc, id desc
            limit %s
            """,
            params,
        )
        rows = cur.fetchall()

    return [
        AggregatorEvidenceRow(
            evidence_id=row["id"],
            source_name=row["source_name"],
            company_key=row["normalized_company_key"],
            company_name=row["company_name"],
            title=row["title"],
            search_profile_name=row["search_profile_name"],
            search_term=row["search_term"],
            evidence_url=row["evidence_url"],
            observed_at=row["observed_at"],
        )
        for row in rows
    ]


def load_known_candidates(conn: psycopg.Connection[Any]) -> list[KnownCompanyCandidate]:
    with conn.cursor(row_factory=dict_row) as cur:
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
        KnownCompanyCandidate(
            candidate_id=row["id"],
            company_key=row["company_key"],
            company_name=row["company_name"],
            status=row["status"],
            source_family_candidate=row["source_family_candidate"],
        )
        for row in rows
    ]


def load_known_vocabulary_terms(conn: psycopg.Connection[Any]) -> dict[str, set[str]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select company_key, observed_term
            from company_vocabulary_observations
            """
        )
        rows = cur.fetchall()

    terms: dict[str, set[str]] = {}
    for row in rows:
        terms.setdefault(str(row["company_key"]), set()).add(str(row["observed_term"]))
    return terms


def load_previous_snapshot(
    conn: psycopg.Connection[Any],
    *,
    source_name: str,
    search_profile_name: str | None,
    search_term: str | None,
) -> PreviousNoveltySnapshot | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select id
            from aggregator_novelty_snapshots
            where source_name = %s
              and cycle_scope = %s
              and search_profile_name is not distinct from %s
              and search_term is not distinct from %s
            order by created_at desc, id desc
            limit 1
            """,
            (source_name, CYCLE_SCOPE, search_profile_name, search_term),
        )
        snapshot_row = cur.fetchone()
        if not snapshot_row:
            return None

        snapshot_id = int(snapshot_row["id"])
        cur.execute(
            """
            select item_type, company_key, observed_term, evidence
            from aggregator_novelty_items
            where snapshot_id = %s
            """,
            (snapshot_id,),
        )
        rows = cur.fetchall()

    company_keys: set[str] = set()
    company_term_keys: set[str] = set()
    for row in rows:
        company_key = row["company_key"]
        if row["item_type"] == "company" and company_key:
            company_keys.add(str(company_key))
        if row["item_type"] == "term" and company_key and row["observed_term"]:
            evidence = row["evidence"] or {}
            term_key = evidence.get("term_key") if isinstance(evidence, dict) else None
            company_term_keys.add(str(term_key or f"{company_key}::{row['observed_term']}"))

    return PreviousNoveltySnapshot(
        snapshot_id=snapshot_id,
        company_keys=frozenset(company_keys),
        company_term_keys=frozenset(company_term_keys),
    )


def _json_default(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def write_snapshot(
    conn: psycopg.Connection[Any],
    *,
    snapshot: AggregatorNoveltySnapshot,
    reviewed_by: str,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into aggregator_novelty_snapshots (
                source_name,
                search_profile_name,
                search_term,
                cycle_scope,
                previous_snapshot_id,
                observed_since,
                observed_until,
                evidence_count,
                distinct_company_count,
                unregistered_company_count,
                known_candidate_company_count,
                newly_observed_company_count,
                repeated_observed_company_count,
                reassessment_company_count,
                new_vocabulary_term_count,
                known_vocabulary_term_count,
                newly_observed_term_count,
                repeated_observed_term_count,
                novelty_score,
                saturation_level,
                recommended_action,
                reason,
                evidence,
                reviewed_by
            ) values (
                %s, %s, %s, %s, %s,
                %s::timestamptz, %s::timestamptz,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s::jsonb, %s
            )
            returning id
            """,
            (
                snapshot.source_name,
                snapshot.search_profile_name,
                snapshot.search_term,
                snapshot.cycle_scope,
                snapshot.previous_snapshot_id,
                snapshot.observed_since,
                snapshot.observed_until,
                snapshot.evidence_count,
                snapshot.distinct_company_count,
                snapshot.unregistered_company_count,
                snapshot.known_candidate_company_count,
                snapshot.newly_observed_company_count,
                snapshot.repeated_observed_company_count,
                snapshot.reassessment_company_count,
                snapshot.new_vocabulary_term_count,
                snapshot.known_vocabulary_term_count,
                snapshot.newly_observed_term_count,
                snapshot.repeated_observed_term_count,
                snapshot.novelty_score,
                snapshot.saturation_level,
                snapshot.recommended_action,
                snapshot.reason,
                json.dumps(snapshot.evidence, ensure_ascii=False, default=_json_default),
                reviewed_by,
            ),
        )
        snapshot_id = cur.fetchone()[0]

        for item in snapshot.items:
            cur.execute(
                """
                insert into aggregator_novelty_items (
                    snapshot_id,
                    item_type,
                    novelty_state,
                    source_name,
                    company_key,
                    company_name,
                    title,
                    search_profile_name,
                    search_term,
                    observed_term,
                    known_candidate_id,
                    known_candidate_status,
                    evidence_url,
                    observed_at,
                    evidence
                ) values (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::timestamptz, %s::jsonb
                )
                """,
                (
                    snapshot_id,
                    item.item_type,
                    item.novelty_state,
                    item.source_name,
                    item.company_key,
                    item.company_name,
                    item.title,
                    item.search_profile_name,
                    item.search_term,
                    item.observed_term,
                    item.known_candidate_id,
                    item.known_candidate_status,
                    item.evidence_url,
                    item.observed_at,
                    json.dumps(item.evidence or {}, ensure_ascii=False, default=_json_default),
                ),
            )

    conn.commit()
    return int(snapshot_id)


def _cycle_state(item: AggregatorNoveltyItem) -> str | None:
    evidence = item.evidence or {}
    value = evidence.get("cycle_novelty_state")
    return str(value) if value else None


def _group_company_items(items: list[AggregatorNoveltyItem]) -> list[tuple[str, str, int, list[str], str | None]]:
    grouped: dict[str, dict[str, object]] = {}
    for item in items:
        if not item.company_key:
            continue
        entry = grouped.setdefault(
            item.company_key,
            {
                "company_name": item.company_name or "-",
                "count": 0,
                "titles": [],
                "status": item.known_candidate_status,
            },
        )
        entry["count"] = int(entry["count"]) + 1
        titles = entry["titles"]
        if isinstance(titles, list) and item.title and item.title not in titles and len(titles) < 3:
            titles.append(item.title)
        if item.known_candidate_status:
            entry["status"] = item.known_candidate_status

    rows: list[tuple[str, str, int, list[str], str | None]] = []
    for company_key, entry in grouped.items():
        rows.append(
            (
                company_key,
                str(entry["company_name"]),
                int(entry["count"]),
                list(entry["titles"]),
                str(entry["status"]) if entry.get("status") else None,
            )
        )
    return sorted(rows, key=lambda row: (-row[2], row[0]))


def render_report(snapshot: AggregatorNoveltySnapshot, *, write_mode: bool) -> str:
    lines = ["S6B Aggregator Novelty Loop Foundation"]
    lines.append(f"source_name: {snapshot.source_name}")
    if snapshot.search_profile_name:
        lines.append(f"search_profile_name: {snapshot.search_profile_name}")
    if snapshot.search_term:
        lines.append(f"search_term: {snapshot.search_term}")
    lines.append(f"previous_snapshot_id: {snapshot.previous_snapshot_id or '-'}")
    lines.append(f"evidence_count: {snapshot.evidence_count}")
    lines.append(f"distinct_company_count: {snapshot.distinct_company_count}")
    lines.append(f"unregistered_company_count: {snapshot.unregistered_company_count}")
    lines.append(f"known_candidate_company_count: {snapshot.known_candidate_company_count}")
    lines.append(f"newly_observed_company_count: {snapshot.newly_observed_company_count}")
    lines.append(f"repeated_observed_company_count: {snapshot.repeated_observed_company_count}")
    lines.append(f"reassessment_company_count: {snapshot.reassessment_company_count}")
    lines.append(f"new_vocabulary_term_count: {snapshot.new_vocabulary_term_count}")
    lines.append(f"known_vocabulary_term_count: {snapshot.known_vocabulary_term_count}")
    lines.append(f"newly_observed_term_count: {snapshot.newly_observed_term_count}")
    lines.append(f"repeated_observed_term_count: {snapshot.repeated_observed_term_count}")
    lines.append(f"novelty_score: {snapshot.novelty_score}")
    lines.append(f"saturation_level: {snapshot.saturation_level}")
    lines.append(f"recommended_action: {snapshot.recommended_action}")
    lines.append(f"reason: {snapshot.reason}")
    lines.append(f"write_mode: {str(write_mode).lower()}")
    lines.append("boundary: no pagination, no search-profile mutation, no source activation, no Bronze write, no scheduler change")

    company_items = [item for item in snapshot.items if item.item_type == "company"]
    newly_observed = [item for item in company_items if _cycle_state(item) == "newly_observed_company"]
    unregistered_backlog = [
        item
        for item in company_items
        if item.novelty_state == "unregistered_company" and _cycle_state(item) != "newly_observed_company"
    ]
    top_reassessments = [item for item in snapshot.items if item.novelty_state == "known_candidate_reassessment"]
    newly_observed_terms = [
        item for item in snapshot.items if item.item_type == "term" and _cycle_state(item) == "newly_observed_term"
    ][:15]

    if newly_observed:
        lines.append("newly_observed_companies:")
        for company_key, company_name, count, titles, _ in _group_company_items(newly_observed)[:10]:
            lines.append(f"- {company_key} | {company_name} | evidence_count={count} | samples={'; '.join(titles)}")
    if unregistered_backlog:
        lines.append("unregistered_company_backlog:")
        for company_key, company_name, count, titles, _ in _group_company_items(unregistered_backlog)[:10]:
            lines.append(f"- {company_key} | {company_name} | evidence_count={count} | samples={'; '.join(titles)}")
    if top_reassessments:
        lines.append("known_candidate_reassessment:")
        for company_key, company_name, count, titles, status in _group_company_items(top_reassessments)[:10]:
            lines.append(f"- {company_key} | {status} | evidence_count={count} | samples={'; '.join(titles)}")
    if newly_observed_terms:
        lines.append("newly_observed_terms:")
        for item in newly_observed_terms:
            lines.append(f"- {item.company_key}: {item.observed_term} | {item.title}")

    if not write_mode:
        lines.append("NEXT: review the novelty assessment, then rerun with --write to persist the snapshot.")
    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.dsn()) as conn:
        previous_snapshot = load_previous_snapshot(
            conn,
            source_name=args.source_name,
            search_profile_name=args.search_profile_name,
            search_term=args.search_term,
        )
        rows = load_market_evidence(
            conn,
            source_name=args.source_name,
            search_profile_name=args.search_profile_name,
            search_term=args.search_term,
            days=args.days,
            limit=args.limit,
        )
        snapshot = build_aggregator_novelty_snapshot(
            rows=rows,
            known_candidates=load_known_candidates(conn),
            known_vocabulary_terms=load_known_vocabulary_terms(conn),
            source_name=args.source_name,
            search_profile_name=args.search_profile_name,
            search_term=args.search_term,
            previous_snapshot=previous_snapshot,
        )
        print(render_report(snapshot, write_mode=args.write))
        if args.write:
            snapshot_id = write_snapshot(conn, snapshot=snapshot, reviewed_by=args.reviewed_by)
            print(f"aggregator_novelty_snapshot_id: {snapshot_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Assess bounded aggregator novelty and saturation from existing market evidence.")
    parser.add_argument("--source-name", default="stepstone", help="Aggregator/source name to assess.")
    parser.add_argument("--search-profile-name", help="Optional search-profile filter.")
    parser.add_argument("--search-term", help="Optional search-term filter.")
    parser.add_argument("--days", type=int, default=14, help="Observation window in days.")
    parser.add_argument("--limit", type=int, default=500, help="Maximum market evidence rows to inspect.")
    parser.add_argument("--write", action="store_true", help="Persist novelty snapshot and items.")
    parser.add_argument("--reviewed-by", default="agent", help="Reviewer/agent label for persisted snapshot.")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
