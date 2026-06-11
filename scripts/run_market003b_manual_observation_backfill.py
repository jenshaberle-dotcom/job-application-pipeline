#!/usr/bin/env python3
"""MARKET-003B manual observation backfill.

Dry-run by default. With --write it performs only bounded market_evidence writes:
new manual observation inserts and legacy manual evidence provenance updates. It
never ingests jobs, writes Bronze/Silver/Gold, creates candidates, mutates gates,
activates sources, builds connectors or changes scheduler state.
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
from src.search_intelligence.market003b_manual_observation_backfill import (
    DEFAULT_MANUAL_OBSERVATION_BACKFILL_SEEDS,
    ManualMarketObservationPlan,
    build_market003b_report,
    render_market003b_markdown,
    seeds_to_insert,
)


def connect() -> Any:
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def load_existing_manual_observations(conn: Any) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select
                id,
                normalized_company_key,
                company_name,
                title,
                evidence_kind,
                evidence ->> 'input_mode' as input_mode
            from market_evidence
            where evidence_kind = 'manual_market_observation'
               or evidence ->> 'input_mode' = 'manual_market_observation'
               or evidence ->> 'observation_origin' = 'external_market_observation'
            order by id
            """
        )
        return [dict(row) for row in cur.fetchall()]


def load_legacy_manual_evidence(conn: Any) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select
                id,
                normalized_company_key,
                company_name,
                title,
                evidence_kind,
                evidence ->> 'input_mode' as input_mode
            from market_evidence
            where evidence_kind = 'manual_aggregator_sighting'
               or evidence ->> 'input_mode' = 'manual_market_evidence'
            order by id
            """
        )
        return [dict(row) for row in cur.fetchall()]


def insert_manual_observation(conn: Any, plan: ManualMarketObservationPlan) -> int | None:
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
    return None if row is None else int(row["id"])


def migrate_legacy_manual_evidence(conn: Any) -> list[int]:
    migration_payload = {
        "input_mode": "manual_market_observation",
        "observation_origin": "external_market_observation",
        "legacy_input_mode": "manual_market_evidence",
        "legacy_evidence_kind": "manual_aggregator_sighting",
        "legacy_migration_work_item": "MARKET-003B",
        "legacy_migration_status": "normalized_to_manual_market_observation",
        "decision_boundary": "learning_signal_only_not_gate_truth",
        "boundary": {
            "job_ingestion": False,
            "bronze_write": False,
            "silver_gold_mutation": False,
            "candidate_creation": False,
            "gate_decision": False,
            "connector_build_or_registration": False,
            "scheduler_change": False,
        },
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            update market_evidence
               set evidence_source = 'manual_market_observation',
                   evidence_kind = 'manual_market_observation',
                   evidence = evidence || %s::jsonb
             where evidence_kind = 'manual_aggregator_sighting'
                or evidence ->> 'input_mode' = 'manual_market_evidence'
            returning id
            """,
            (json.dumps(migration_payload, ensure_ascii=False, sort_keys=True),),
        )
        return [int(row["id"]) for row in cur.fetchall()]


def write_report(report: dict[str, Any], *, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"market003b_manual_observation_backfill_{stamp}.json"
    md_path = output_dir / f"market003b_manual_observation_backfill_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_market003b_markdown(report), encoding="utf-8")
    return json_path, md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill manual market observations and normalize legacy manual evidence.")
    parser.add_argument("--write", action="store_true", help="Persist bounded market_evidence inserts/updates. Dry-run by default.")
    parser.add_argument("--output-dir", default="exports")
    parser.add_argument("--list-default-companies", action="store_true", help="Print the code-backed backfill inventory and exit.")
    return parser


def run(args: argparse.Namespace) -> int:
    seeds = DEFAULT_MANUAL_OBSERVATION_BACKFILL_SEEDS
    if args.list_default_companies:
        for seed in seeds:
            print(f"{seed.company_key}\t{seed.company_name}")
        return 0

    with connect() as conn:
        existing_rows = load_existing_manual_observations(conn)
        legacy_rows = load_legacy_manual_evidence(conn)
        migrated_ids: list[int] = []
        written_ids_by_company_key: dict[str, int | None] = {}
        if args.write:
            # Build the write set from the pre-write review state so legacy rows
            # cover their company seeds and are not duplicated by later inserts.
            plans = seeds_to_insert(seeds, existing_manual_rows=existing_rows, legacy_rows=legacy_rows)
            migrated_ids = migrate_legacy_manual_evidence(conn)
            for plan in plans:
                written_ids_by_company_key[plan.company_key] = insert_manual_observation(conn, plan)
            conn.commit()
            report = build_market003b_report(
                seeds=seeds,
                existing_manual_rows=existing_rows,
                legacy_rows=legacy_rows,
                write=True,
                written_ids_by_company_key=written_ids_by_company_key,
                migrated_legacy_ids=migrated_ids,
            ).as_dict()
        else:
            report = build_market003b_report(
                seeds=seeds,
                existing_manual_rows=existing_rows,
                legacy_rows=legacy_rows,
                write=False,
            ).as_dict()

    json_path, md_path = write_report(report, output_dir=Path(args.output_dir))
    summary = report["summary"]
    print("# MARKET-003B Manual Observation Backfill")
    print("boundary: dry-run by default; --write is limited to market_evidence inserts/legacy provenance updates only")
    print(f"write={str(args.write).lower()}")
    for key, value in summary.items():
        print(f"{key}={value}")
    print(f"next_action={report['next_action']}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    return 0


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
