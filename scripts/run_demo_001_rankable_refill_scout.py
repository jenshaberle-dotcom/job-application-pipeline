"""Read-only DEMO-001 scout for real, current employer-origin rankable refill candidates.

The scout never creates Product authority. It reads current Product V1 rows from
active recurring employer-origin sources, probes each exact vacancy URL live and
compares the returned detail text with approved Candidate Fact capability tags.
The output is an evidence shortlist for the existing guarded Assessment ->
Capability Fit -> Hard Filter -> Ranking writers.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from scripts.run_product_v1_assessment_materialization import (
    authorized_recurring_employer_origin_sources,
)
from src.config import get_database_config
from src.ingestion.repository import JobIngestionRepository
from src.job_lifecycle_health import (
    OUTCOME_SEEN_ACTIVE,
    JobLifecycleHealthRepository,
    classify_exact_detail,
    fetch_exact_detail,
)
from src.search_intelligence.product_v1_application_context import (
    CandidateFactSnapshot,
    _job_references_for_fact,
)
from src.search_intelligence.product_v1_contenders import classify_role_title


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".runtime" / "demo" / "demo_001_rankable_refill_scout.json"
CAPABILITY_EVIDENCE_CLASSES = frozenset(
    {
        "professional_employment",
        "formal_education",
        "portfolio_implementation",
        "training_certification",
    }
)
READINESS_PRIORITY = {
    "rankable": 0,
    "hard_filter_evidence_required": 1,
    "assessment_required": 2,
}


def _load_candidate_facts(conn: psycopg.Connection[Any]) -> tuple[CandidateFactSnapshot, ...]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                fact_key,
                category,
                evidence_class,
                approval_status,
                statement,
                capability_tags,
                limitations,
                valid_from,
                valid_until
            FROM candidate_facts
            WHERE profile_key = 'default'
              AND approval_status = 'approved'
            ORDER BY fact_key
            """
        )
        rows = cur.fetchall()
    today = date.today()
    facts: list[CandidateFactSnapshot] = []
    for row in rows:
        fact = CandidateFactSnapshot(
            fact_key=str(row["fact_key"]),
            category=str(row["category"]),
            evidence_class=str(row["evidence_class"]),
            approval_status=str(row["approval_status"]),
            statement=str(row["statement"]),
            capability_tags=tuple(str(value) for value in (row["capability_tags"] or ())),
            limitations=tuple(str(value) for value in (row["limitations"] or ())),
            valid_from=row["valid_from"],
            valid_until=row["valid_until"],
        )
        if fact.evidence_class in CAPABILITY_EVIDENCE_CLASSES and fact.is_valid_on(today):
            facts.append(fact)
    return tuple(facts)


def _load_rows(
    conn: psycopg.Connection[Any],
    *,
    authorized_sources: Sequence[str],
    limit: int,
) -> list[dict[str, object]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                readiness.silver_job_id,
                readiness.company_name,
                readiness.title,
                readiness.source_name,
                readiness.source_url,
                readiness.canonical_source_type,
                readiness.lifecycle_status,
                readiness.origin_validation_status,
                readiness.activity_status,
                readiness.hard_filter_status,
                readiness.product_readiness_status,
                readiness.overall_quality_score,
                assessment.capability_fit_status
            FROM gold_product_v1_job_readiness readiness
            LEFT JOIN job_product_assessments assessment
              ON assessment.silver_job_id = readiness.silver_job_id
            WHERE readiness.lifecycle_status = 'active_confirmed'
              AND readiness.source_name = ANY(%s)
              AND readiness.product_readiness_status IN (
                    'assessment_required',
                    'hard_filter_evidence_required',
                    'rankable'
              )
              AND NULLIF(btrim(readiness.source_url), '') IS NOT NULL
            ORDER BY
                CASE readiness.product_readiness_status
                    WHEN 'rankable' THEN 0
                    WHEN 'hard_filter_evidence_required' THEN 1
                    ELSE 2
                END,
                readiness.overall_quality_score DESC NULLS LAST,
                readiness.silver_job_id DESC
            LIMIT %s
            """,
            (list(authorized_sources), limit),
        )
        return [dict(row) for row in cur.fetchall()]


def _capability_matches(
    *,
    detail_text: str,
    facts: Sequence[CandidateFactSnapshot],
) -> tuple[list[dict[str, object]], set[str]]:
    matches: list[dict[str, object]] = []
    tags: set[str] = set()
    for fact in facts:
        references = _job_references_for_fact(fact=fact, detail_text=detail_text)
        if not references:
            continue
        matched_tags = sorted({reference.capability_tag for reference in references})
        tags.update(matched_tags)
        matches.append(
            {
                "fact_key": fact.fact_key,
                "matched_capability_tags": matched_tags,
                "exact_job_evidence": sorted({reference.evidence for reference in references})[:8],
            }
        )
    return matches, tags


def scout(
    *,
    rows: Sequence[Mapping[str, object]],
    facts: Sequence[CandidateFactSnapshot],
) -> list[dict[str, object]]:
    health_repository = JobLifecycleHealthRepository()
    results: list[dict[str, object]] = []
    for row in rows:
        silver_job_id = int(row["silver_job_id"])
        item: dict[str, object] = {str(key): value for key, value in row.items()}
        item.update(
            {
                "live_outcome": "unverifiable",
                "live_final_url": None,
                "live_reason": None,
                "matched_fact_count": 0,
                "matched_capability_tags": [],
                "candidate_fact_matches": [],
                "role_relevant": classify_role_title(str(row.get("title") or "")) is not None,
            }
        )
        try:
            target = health_repository.load_target(silver_job_id)
            probe = fetch_exact_detail(str(row.get("source_url") or ""))
            classification = classify_exact_detail(target, probe)
            item["live_outcome"] = classification.outcome
            item["live_final_url"] = probe.final_url
            item["live_reason"] = classification.evidence_reason
            if classification.outcome == OUTCOME_SEEN_ACTIVE:
                matches, tags = _capability_matches(
                    detail_text=probe.response_text,
                    facts=facts,
                )
                item["candidate_fact_matches"] = matches
                item["matched_fact_count"] = len(matches)
                item["matched_capability_tags"] = sorted(tags)
        except Exception as exc:  # runtime evidence must remain fail-closed
            item["live_reason"] = f"{type(exc).__name__}: {' '.join(str(exc).split())[:300]}"
        results.append(item)

    results.sort(
        key=lambda item: (
            0 if item.get("live_outcome") == OUTCOME_SEEN_ACTIVE else 1,
            0 if item.get("role_relevant") else 1,
            READINESS_PRIORITY.get(str(item.get("product_readiness_status") or ""), 9),
            -int(item.get("matched_fact_count") or 0),
            -len(item.get("matched_capability_tags") or []),
            int(item.get("silver_job_id") or 0),
        )
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.limit < 1 or args.limit > 100:
        raise SystemExit("--limit must be between 1 and 100")

    authorized = sorted(
        authorized_recurring_employer_origin_sources(JobIngestionRepository())
    )
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        facts = _load_candidate_facts(conn)
        rows = _load_rows(conn, authorized_sources=authorized, limit=args.limit)
        conn.rollback()

    results = scout(rows=rows, facts=facts)
    live = [row for row in results if row["live_outcome"] == OUTCOME_SEEN_ACTIVE]
    strong = [
        row
        for row in live
        if row["role_relevant"] and int(row["matched_fact_count"] or 0) > 0
    ]
    payload = {
        "schema": "job_application_pipeline.demo_001_rankable_refill_scout.v1",
        "authorized_source_count": len(authorized),
        "candidate_fact_count": len(facts),
        "candidate_count": len(results),
        "live_active_count": len(live),
        "live_role_and_fact_match_count": len(strong),
        "target_rankable_count": 5,
        "candidates": results,
        "boundaries": {
            "database_reads": True,
            "database_writes": False,
            "network_exact_detail_requests": len(rows),
            "provider_requests": 0,
            "capability_fit_authority_created": False,
            "hard_filter_authority_created": False,
            "ranking_authority_created": False,
            "top5_forced": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("=== DEMO-001 RANKABLE REFILL SCOUT ===")
    print(f"AUTHORIZED_SOURCES={len(authorized)}")
    print(f"APPROVED_CAPABILITY_FACTS={len(facts)}")
    print(f"CANDIDATES={len(results)}")
    print(f"LIVE_ACTIVE={len(live)}")
    print(f"LIVE_ROLE_FACT_MATCH={len(strong)}")
    for row in results[:15]:
        print(
            "CANDIDATE="
            f"{row['silver_job_id']}|{row['live_outcome']}|"
            f"{row['product_readiness_status']}|facts={row['matched_fact_count']}|"
            f"tags={','.join(row['matched_capability_tags'])}|"
            f"{row['source_name']}|{row['company_name']}|{row['title']}|"
            f"{row['live_final_url'] or row['source_url']}"
        )
    print("DATABASE_WRITES=0")
    print("PROVIDER_REQUESTS=0")
    print(f"artifact={args.output.resolve()}")
    print("DEMO_001_RANKABLE_REFILL_SCOUT=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
