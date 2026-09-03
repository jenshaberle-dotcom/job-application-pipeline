"""Fail-closed DEMO-001 refill integrity preflight.

The bounded refill may proceed only when every selected non-rankable live candidate
still has the exact employer-origin detail fingerprint bound to its current Product
assessment. Any detail drift blocks the entire apply before a database mutation.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.run_demo_001_rankable_refill_scout import (
    _load_candidate_facts,
    _load_rows,
    scout,
)
from scripts.run_product_v1_assessment_materialization import (
    authorized_recurring_employer_origin_sources,
)
from src.config import get_database_config
from src.ingestion.repository import JobIngestionRepository
from src.job_lifecycle_health import OUTCOME_SEEN_ACTIVE
from src.search_intelligence.product_v1_assessment_evidence import (
    extract_product_v1_assessment_evidence,
)
from src.search_intelligence.product_v1_downstream_preview import (
    fetch_public_https_detail_text,
)


DEFAULT_CANDIDATE_CAP = 7


def _assessment_rows(conn: psycopg.Connection[Any], ids: list[int]) -> dict[int, dict[str, object]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                readiness.silver_job_id,
                readiness.title,
                readiness.source_url,
                readiness.product_readiness_status,
                assessment.ranking_factors
            FROM gold_product_v1_job_readiness readiness
            JOIN job_product_assessments assessment
              ON assessment.silver_job_id = readiness.silver_job_id
            WHERE readiness.silver_job_id = ANY(%s)
            """,
            (ids,),
        )
        return {int(row["silver_job_id"]): dict(row) for row in cur.fetchall()}


def _selected(rows: list[dict[str, object]], cap: int) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for row in rows:
        if row.get("live_outcome") != OUTCOME_SEEN_ACTIVE:
            continue
        if not bool(row.get("role_relevant")):
            continue
        matches = row.get("candidate_fact_matches")
        if not isinstance(matches, list) or not matches:
            continue
        result.append(row)
        if len(result) >= cap:
            break
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-cap", type=int, default=DEFAULT_CANDIDATE_CAP)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not 1 <= args.candidate_cap <= 15:
        raise SystemExit("--candidate-cap must be between 1 and 15")

    authorized = sorted(
        authorized_recurring_employer_origin_sources(JobIngestionRepository())
    )
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        facts = _load_candidate_facts(conn)
        candidates = _load_rows(
            conn,
            authorized_sources=authorized,
            limit=max(30, args.candidate_cap * 4),
        )
        conn.rollback()

    selected = _selected(scout(rows=candidates, facts=facts), args.candidate_cap)
    ids = [int(row["silver_job_id"]) for row in selected]
    if not ids:
        raise SystemExit("no live Candidate-Fact-backed refill candidates")

    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        assessments = _assessment_rows(conn, ids)
        conn.rollback()

    checked = 0
    drifted = 0
    for row in selected:
        job_id = int(row["silver_job_id"])
        current = assessments.get(job_id)
        if current is None:
            print(f"INTEGRITY={job_id}|BLOCKED|assessment_missing")
            drifted += 1
            continue
        if str(current.get("product_readiness_status") or "") == "rankable":
            print(f"INTEGRITY={job_id}|PASS|already_rankable")
            checked += 1
            continue
        ranking_factors = current.get("ranking_factors")
        expected = (
            str(ranking_factors.get("detail_description_sha256") or "").strip()
            if isinstance(ranking_factors, dict)
            else ""
        )
        if len(expected) != 64:
            print(f"INTEGRITY={job_id}|BLOCKED|assessment_detail_sha_missing")
            drifted += 1
            continue
        source_url = str(current.get("source_url") or "")
        title = str(current.get("title") or "")
        final_url, _page_title, detail_text = fetch_public_https_detail_text(source_url)
        live = extract_product_v1_assessment_evidence(
            description=detail_text,
            title=title,
            source_url=final_url,
        ).description_sha256
        if live != expected:
            print(
                f"INTEGRITY={job_id}|BLOCKED|detail_drift|expected={expected[:12]}|live={live[:12]}"
            )
            drifted += 1
            continue
        print(f"INTEGRITY={job_id}|PASS|detail_sha={live[:12]}")
        checked += 1

    print(f"SELECTED={len(selected)}")
    print(f"PASS={checked}")
    print(f"BLOCKED={drifted}")
    print("DATABASE_WRITES=0")
    print("PROVIDER_REQUESTS=0")
    if drifted:
        print("DEMO_001_RANKABLE_REFILL_INTEGRITY=BLOCKED")
        return 2
    print("DEMO_001_RANKABLE_REFILL_INTEGRITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
