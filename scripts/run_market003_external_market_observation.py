#!/usr/bin/env python3
"""MARKET-003 External Market Observation Foundation.

Dry-run by default. With --write it performs an explicit, bounded database write
to market_evidence only. It does not ingest a job, write Bronze/Silver/Gold,
create candidates, mutate gates, activate sources, register connectors or change
the scheduler.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import get_database_config
from src.search_intelligence.market003_external_market_observations import (
    ManualMarketObservationInput,
    build_manual_market_observation_plan,
    build_manual_market_observation_review,
    render_market003_markdown,
)


def connect() -> Any:
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def insert_manual_observation(conn: Any, plan: Any) -> int | None:
    if not plan.insert_allowed:
        raise ValueError(f"Refusing insert for action={plan.action!r}: {plan.reason}")
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into market_evidence (
                evidence_source,
                evidence_kind,
                source_name,
                normalized_company_key,
                company_name,
                title,
                evidence_url,
                search_profile_name,
                search_term,
                source_seen_at,
                evidence
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::timestamptz, %s::jsonb)
            on conflict do nothing
            returning id
            """,
            (
                plan.evidence_source,
                plan.evidence_kind,
                plan.source_name,
                plan.company_key,
                plan.company_name,
                plan.title,
                plan.evidence_url,
                plan.search_profile_name,
                plan.search_term,
                plan.source_seen_at,
                json.dumps(plan.evidence_payload, ensure_ascii=False, sort_keys=True),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return None if row is None else int(row["id"])


def load_manual_observations(conn: Any, *, days: int, limit: int) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select
                id,
                evidence_source,
                evidence_kind,
                source_name,
                normalized_company_key,
                company_name,
                title,
                evidence_url,
                observed_at,
                evidence
            from market_evidence
            where evidence_kind = 'manual_market_observation'
              and observed_at >= now() - (%s || ' days')::interval
            order by observed_at desc, id desc
            limit %s
            """,
            (days, limit),
        )
        return [dict(row) for row in cur.fetchall()]


def write_report(report: dict[str, Any], *, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"market003_external_market_observations_{stamp}.json"
    md_path = output_dir / f"market003_external_market_observations_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_market003_markdown(report), encoding="utf-8")
    return json_path, md_path


def print_plan(plan: Any, *, write: bool, written_id: int | None) -> None:
    print("# MARKET-003 External Market Observation Foundation")
    print("boundary: dry-run by default; --write is limited to market_evidence only; no job ingestion, no Bronze/Silver/Gold write, no candidate creation, no gate decision, no connector activation, no scheduler change")
    print(f"company_key={plan.company_key}")
    print(f"source_name={plan.source_name}")
    print(f"evidence_kind={plan.evidence_kind}")
    print(f"action={plan.action}")
    print(f"insert_allowed={plan.insert_allowed}")
    print(f"write={write}")
    print(f"market_evidence_id={written_id if written_id is not None else '-'}")
    if not write:
        print("dry_run: no market_evidence row written; pass --write after review")
    elif written_id is None:
        print("write_result: duplicate observation already existed")
    else:
        print("write_result: manual market observation persisted as learning signal")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record or review MARKET-003 manual market observations.")
    parser.add_argument("--company-name")
    parser.add_argument("--title")
    parser.add_argument("--observation-channel", default="linkedin")
    parser.add_argument("--observation-source", default="manual_market_observation")
    parser.add_argument("--evidence-url")
    parser.add_argument("--search-term")
    parser.add_argument("--search-profile-name")
    parser.add_argument("--observed-at")
    parser.add_argument("--location")
    parser.add_argument("--remote-signal", default="unknown")
    parser.add_argument("--relevance-signal", default="unknown")
    parser.add_argument("--note")
    parser.add_argument("--recorded-by", default="jens")
    parser.add_argument("--write", action="store_true", help="Persist one manual observation to market_evidence only. Dry-run by default.")
    parser.add_argument("--review-only", action="store_true", help="Read existing manual observations and write only JSON/Markdown review outputs.")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--output-dir", default="exports")
    return parser


def run(args: argparse.Namespace) -> int:
    written_id: int | None = None
    if not args.review_only:
        if not args.company_name or not args.title:
            raise SystemExit("--company-name and --title are required unless --review-only is used.")
        observation = ManualMarketObservationInput(
            company_name=args.company_name,
            title=args.title,
            observation_channel=args.observation_channel,
            observation_source=args.observation_source,
            evidence_url=args.evidence_url,
            search_term=args.search_term,
            search_profile_name=args.search_profile_name,
            observed_at=args.observed_at,
            location=args.location,
            remote_signal=args.remote_signal,
            relevance_signal=args.relevance_signal,
            note=args.note,
            recorded_by=args.recorded_by,
        )
        plan = build_manual_market_observation_plan(observation)
        if args.write:
            with connect() as conn:
                written_id = insert_manual_observation(conn, plan)
        print_plan(plan, write=args.write, written_id=written_id)
        return 0

    with connect() as conn:
        rows = load_manual_observations(conn, days=args.days, limit=args.limit)
    report = build_manual_market_observation_review(rows).as_dict()
    json_path, md_path = write_report(report, output_dir=Path(args.output_dir))
    print("# MARKET-003 External Market Observation Review")
    print(f"observation_count={report['observation_count']}")
    print(f"distinct_company_count={report['distinct_company_count']}")
    print(f"strong_relevant_company_count={report['strong_relevant_company_count']}")
    print(f"next_action={report['next_action']}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    return 0


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
