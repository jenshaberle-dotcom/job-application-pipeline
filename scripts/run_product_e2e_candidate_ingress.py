"""Plan or explicitly apply generic discovery-to-candidate ingress.

Dry-run is the default.  Apply creates only ``discovery`` employer-origin
candidate rows with an unresolved origin URL.  It never browses, runs gates,
builds connectors, activates sources, ingests jobs or changes scheduling.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import psycopg
from psycopg.rows import dict_row

from scripts.run_origin_observation_seed_pool_agent import collect_seeds
from src.config import get_database_config
from src.search_intelligence.origin_seed_pool import (
    ObservationSeed,
    classify_seed_row,
    deduplicate_seeds,
    normalize_company_key,
)
from src.search_intelligence.product_e2e_candidate_ingress import (
    APPROVAL_TOKEN,
    CandidateIngressPlan,
    ExistingCandidate,
    build_candidate_ingress_plan,
    select_apply_plans,
)
from src.search_intelligence.product_e2e_golden_path import (
    DiscoveryCase,
    case_from_seed,
    select_representative_cases,
)

PLAN_RESULT = "PRODUCT_E2E_CANDIDATE_INGRESS_PLAN_COMPLETED"
APPLY_RESULT = "PRODUCT_E2E_CANDIDATE_INGRESS_APPLY_COMPLETED"


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def relation_exists(conn: psycopg.Connection[Any], name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            ) AS present
            """,
            (name,),
        )
        row = cur.fetchone()
    return bool(row and row["present"])


def collect_manual_observation_seeds(
    conn: psycopg.Connection[Any],
    *,
    limit: int,
) -> list[ObservationSeed]:
    """Collect manual observations independently of the general evidence limit."""

    if not relation_exists(conn, "market_evidence"):
        return []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                'manual_market_observation' AS seed_source_table,
                normalized_company_key AS company_key,
                company_name,
                source_name,
                evidence_url AS seed_url
            FROM market_evidence
            WHERE evidence_kind = 'manual_market_observation'
               OR evidence_source = 'manual_market_observation'
               OR evidence ->> 'input_mode' = 'manual_market_observation'
               OR evidence ->> 'observation_origin' = 'external_market_observation'
            ORDER BY source_seen_at DESC NULLS LAST, id DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = [dict(row) for row in cur.fetchall()]
    return [classify_seed_row(row) for row in rows]


def collect_portfolio_cases(
    conn: psycopg.Connection[Any],
    *,
    limit: int,
    limit_per_seed_source: int,
    manual_limit: int,
) -> list[DiscoveryCase]:
    seeds = collect_seeds(conn, limit_per_source=limit_per_seed_source)
    manual_seeds = collect_manual_observation_seeds(conn, limit=manual_limit)
    combined = deduplicate_seeds([*seeds, *manual_seeds])
    return select_representative_cases(
        (case_from_seed(seed) for seed in combined),
        limit=limit,
    )


def load_existing_candidate(
    conn: psycopg.Connection[Any],
    case: DiscoveryCase,
) -> ExistingCandidate | None:
    if not relation_exists(conn, "employer_origin_source_candidates"):
        return None
    company_key = normalize_company_key(case.company_key or case.company_name)
    with conn.cursor() as cur:
        if company_key:
            cur.execute(
                """
                SELECT id, company_key, company_name, status
                FROM employer_origin_source_candidates
                WHERE lower(company_key) = lower(%s)
                ORDER BY updated_at DESC NULLS LAST, id DESC
                LIMIT 1
                """,
                (company_key,),
            )
            row = cur.fetchone()
            if row is not None:
                return ExistingCandidate(
                    candidate_id=int(row["id"]),
                    company_key=str(row["company_key"]),
                    company_name=str(row["company_name"]),
                    status=str(row["status"]),
                )
        if not case.company_name:
            return None
        cur.execute(
            """
            SELECT id, company_key, company_name, status
            FROM employer_origin_source_candidates
            WHERE lower(company_name) = lower(%s)
            ORDER BY updated_at DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (case.company_name,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return ExistingCandidate(
        candidate_id=int(row["id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        status=str(row["status"]),
    )


def build_plans(
    conn: psycopg.Connection[Any],
    cases: Iterable[DiscoveryCase],
) -> list[CandidateIngressPlan]:
    return [
        build_candidate_ingress_plan(case, load_existing_candidate(conn, case))
        for case in cases
    ]


def insert_candidate(
    conn: psycopg.Connection[Any],
    plan: CandidateIngressPlan,
    *,
    reviewed_by: str,
) -> int | None:
    if not plan.company_key or not plan.company_name:
        raise ValueError("Refusing candidate creation without company identity.")
    if not plan.create_allowed_after_explicit_approval:
        raise ValueError(f"Refusing candidate creation for action={plan.action!r}.")

    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (plan.company_key,))
        cur.execute(
            """
            SELECT id
            FROM employer_origin_source_candidates
            WHERE lower(company_key) = lower(%s)
               OR lower(company_name) = lower(%s)
            ORDER BY id DESC
            LIMIT 1
            """,
            (plan.company_key, plan.company_name),
        )
        existing = cur.fetchone()
        if existing is not None:
            return None

        cur.execute(
            """
            INSERT INTO employer_origin_source_candidates (
                company_key,
                company_name,
                candidate_url,
                source_name_candidate,
                source_family_candidate,
                source_target_candidate,
                source_type_candidate,
                status,
                risk_level,
                notes,
                updated_at
            ) VALUES (%s, %s, NULL, %s, %s, NULL, %s, 'discovery', %s, %s, now())
            RETURNING id
            """,
            (
                plan.company_key,
                plan.company_name,
                plan.source_name_candidate,
                plan.source_family_candidate,
                plan.source_type_candidate,
                plan.risk_level,
                (
                    "Created by PRODUCT-E2E-INGRESS-001 from a generic discovery "
                    f"signal; discovery_source_class={plan.discovery_source_class}; "
                    f"seed_type={plan.seed_type}; seed_source_table={plan.seed_source_table}; "
                    f"case_id={plan.case_id}; reviewed_by={reviewed_by}. "
                    "Origin URL intentionally remains NULL and no gate decision is implied."
                ),
            ),
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("Candidate insert returned no id.")
    return int(row["id"])


def apply_selected_plans(
    conn: psycopg.Connection[Any],
    plans: Iterable[CandidateIngressPlan],
    *,
    reviewed_by: str,
) -> dict[str, int | None]:
    result: dict[str, int | None] = {}
    for plan in plans:
        assert plan.company_key is not None
        result[plan.company_key] = insert_candidate(
            conn,
            plan,
            reviewed_by=reviewed_by,
        )
    conn.commit()
    return result


def write_report(
    plans: list[CandidateIngressPlan],
    *,
    selected_apply_keys: Iterable[str],
    created_ids: Mapping[str, int | None],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_dir / f"product_e2e_candidate_ingress_{stamp}.json"
    payload = {
        "schema_version": "product_e2e_candidate_ingress.v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "review_output_only_not_pipeline_input": True,
        "selected_apply_company_keys": list(selected_apply_keys),
        "created_candidate_ids": dict(created_ids),
        "plans": [asdict(plan) for plan in plans],
        "boundary": {
            "dry_run_default": True,
            "explicit_company_keys_required_for_apply": True,
            "exact_approval_token_required": True,
            "candidate_status_created": "discovery",
            "origin_url_written": False,
            "gate_decision_written": False,
            "connector_built_or_registered": False,
            "source_activated": False,
            "bronze_or_silver_written": False,
            "scheduler_changed": False,
        },
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan or explicitly create generic discovery-state origin candidates."
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--limit-per-seed-source", type=int, default=100)
    parser.add_argument("--manual-limit", type=int, default=50)
    parser.add_argument("--company-key", action="append", default=[])
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--include-manual-observations", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    if args.limit < 1 or args.limit > 5:
        raise SystemExit("--limit must be between 1 and 5")
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit(f"--apply requires --approval-token {APPROVAL_TOKEN}")
    if args.apply and not args.company_key:
        raise SystemExit("--apply requires at least one explicit --company-key")

    with connect() as conn:
        cases = collect_portfolio_cases(
            conn,
            limit=args.limit,
            limit_per_seed_source=args.limit_per_seed_source,
            manual_limit=args.manual_limit,
        )
        plans = build_plans(conn, cases)
        selected: tuple[CandidateIngressPlan, ...] = ()
        created_ids: dict[str, int | None] = {}
        if args.apply:
            try:
                selected = select_apply_plans(
                    plans,
                    requested_company_keys=args.company_key,
                    include_manual_observations=args.include_manual_observations,
                )
            except ValueError as exc:
                conn.rollback()
                raise SystemExit(str(exc)) from exc
            created_ids = apply_selected_plans(
                conn,
                selected,
                reviewed_by=args.reviewed_by,
            )
        else:
            conn.rollback()

    counts: dict[str, int] = {}
    for plan in plans:
        counts[plan.plan_status] = counts.get(plan.plan_status, 0) + 1

    print("Product E2E generic discovery candidate ingress")
    print(f"portfolio_cases: {len(plans)}/5")
    print(f"plan_status_counts: {json.dumps(dict(sorted(counts.items())), sort_keys=True)}")
    for plan in plans:
        print(
            "plan: "
            f"source={plan.discovery_source_class} | company={plan.company_name or plan.company_key or '-'} | "
            f"action={plan.action} | status={plan.plan_status} | "
            f"apply_eligible={str(plan.create_allowed_after_explicit_approval).lower()}"
        )
    for company_key, candidate_id in created_ids.items():
        print(
            f"apply: company_key={company_key} | "
            f"candidate_id={candidate_id if candidate_id is not None else 'already_exists'}"
        )

    report_path = write_report(
        plans,
        selected_apply_keys=(plan.company_key or "" for plan in selected),
        created_ids=created_ids,
        output_dir=args.output_dir,
    )
    print(f"artifact_json: {report_path}")
    print(f"RESULT: {APPLY_RESULT if args.apply else PLAN_RESULT}")
    return 0


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
