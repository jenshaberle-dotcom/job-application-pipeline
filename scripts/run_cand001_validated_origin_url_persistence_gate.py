from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.run_origin_source_discovery_agent import (
    load_local_env_file,
    run_for_company as run_atomic_origin_discovery,
)
from scripts.run_origin_url_default_repair import run_default_repair_for_company
from src.config import get_database_config
from src.search_intelligence.cand001_validated_origin_url_persistence import (
    CandidatePersistenceSnapshot,
    OriginUrlValidationEvidence,
    build_persistence_plan_item,
    evidence_from_origin_discovery_payload,
    markdown_report,
    normalize_url,
    report_payload,
)

DEFAULT_OUTPUT_DIR = Path("exports/cand001_validated_origin_url_persistence_gate")
REVIEW_TABLE = "candidate_origin_url_persistence_reviews"


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _db_object_exists(conn: psycopg.Connection[Any], object_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("select to_regclass(%s)", (object_name,))
        row = cur.fetchone()
    return bool(row and row["to_regclass"])


def load_candidate(
    conn: psycopg.Connection[Any],
    company_key: str,
    *,
    candidate_id: int | None = None,
) -> CandidatePersistenceSnapshot:
    with conn.cursor(row_factory=dict_row) as cur:
        if candidate_id is None:
            cur.execute(
                """
                SELECT id, company_key, company_name, status, candidate_url, risk_level
                FROM employer_origin_source_candidates
                WHERE company_key = %s
                ORDER BY updated_at DESC NULLS LAST, id DESC
                LIMIT 1
                """,
                (company_key,),
            )
        else:
            cur.execute(
                """
                SELECT id, company_key, company_name, status, candidate_url, risk_level
                FROM employer_origin_source_candidates
                WHERE id = %s
                """,
                (candidate_id,),
            )
        row = cur.fetchone()
    if not row:
        target = (
            f"candidate_id={candidate_id} company_key={company_key!r}"
            if candidate_id is not None
            else f"company_key={company_key!r}"
        )
        raise SystemExit(f"No employer-origin candidate found for {target}.")
    if candidate_id is not None and str(row["company_key"]) != company_key:
        raise SystemExit(
            "Exact candidate identity mismatch: "
            f"candidate_id={candidate_id} has company_key={row['company_key']!r}, "
            f"not {company_key!r}."
        )
    return CandidatePersistenceSnapshot(
        candidate_id=int(row["id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        status=str(row["status"]),
        candidate_url=row["candidate_url"],
        risk_level=row["risk_level"],
    )


def duplicate_selected_url_exists(
    conn: psycopg.Connection[Any],
    *,
    candidate: CandidatePersistenceSnapshot,
    selected_url: str | None,
) -> bool:
    if not selected_url:
        return False
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT 1
            FROM employer_origin_source_candidates
            WHERE company_key = %s
              AND candidate_url = %s
              AND id <> %s
            LIMIT 1
            """,
            (candidate.company_key, selected_url, candidate.candidate_id),
        )
        return cur.fetchone() is not None


def write_review_and_candidate_url(
    conn: psycopg.Connection[Any],
    *,
    item,
    evidence: OriginUrlValidationEvidence,
    reviewed_by: str,
) -> int:
    if not _db_object_exists(conn, REVIEW_TABLE):
        raise SystemExit(
            f"Missing {REVIEW_TABLE}. Apply database migrations before running "
            "CAND-001 with --apply."
        )
    if not item.apply_allowed or not item.selected_url:
        raise SystemExit(f"Apply blocked for {item.company_key}: {item.decision}")

    boundary = {
        "sz1_candidate_metadata_transition": True,
        "explicit_apply_required": True,
        "default_repair_required_before_apply": True,
        "exact_candidate_identity_required": True,
        "no_gate_write": True,
        "no_evidence_write": True,
        "no_connector_registration": True,
        "no_source_activation": True,
        "no_scheduler_change": True,
    }
    evidence_payload = {
        "selected_url_source": item.selected_url_source,
        "url_finder_tier": item.url_finder_tier,
        "url_finder_decision": item.url_finder_decision,
        "confidence_score": item.confidence_score,
        "reason": evidence.reason,
        "risk_level": evidence.risk_level,
    }
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, company_key, status, candidate_url
            FROM employer_origin_source_candidates
            WHERE id = %s
            FOR UPDATE
            """,
            (item.candidate_id,),
        )
        locked = cur.fetchone()
        if locked is None:
            raise SystemExit(
                f"Exact candidate {item.candidate_id} disappeared before URL apply."
            )
        if str(locked["company_key"]) != item.company_key:
            raise SystemExit(
                "Exact candidate company_key drift before URL apply: "
                f"candidate_id={item.candidate_id} expected={item.company_key!r} "
                f"actual={locked['company_key']!r}."
            )
        if str(locked["status"]) != item.candidate_status:
            raise SystemExit(
                "Exact candidate status drift before URL apply: "
                f"candidate_id={item.candidate_id} expected={item.candidate_status!r} "
                f"actual={locked['status']!r}."
            )
        if normalize_url(locked["candidate_url"]) != normalize_url(
            item.previous_candidate_url
        ):
            raise SystemExit(
                "Exact candidate URL drift before URL apply: "
                f"candidate_id={item.candidate_id}."
            )

        cur.execute(
            """
            INSERT INTO candidate_origin_url_persistence_reviews (
                candidate_id,
                company_key,
                company_name,
                previous_candidate_url,
                selected_candidate_url,
                selected_url_source,
                decision,
                review_status,
                reason,
                boundary,
                evidence,
                reviewed_by,
                applied_at
            )
            VALUES (
                %(candidate_id)s,
                %(company_key)s,
                %(company_name)s,
                %(previous_candidate_url)s,
                %(selected_url)s,
                %(selected_url_source)s,
                %(decision)s,
                'applied',
                %(reason)s,
                %(boundary)s::jsonb,
                %(evidence)s::jsonb,
                %(reviewed_by)s,
                now()
            )
            RETURNING id
            """,
            {
                "candidate_id": item.candidate_id,
                "company_key": item.company_key,
                "company_name": item.company_name,
                "previous_candidate_url": item.previous_candidate_url,
                "selected_url": item.selected_url,
                "selected_url_source": item.selected_url_source,
                "decision": item.decision,
                "reason": item.reason,
                "boundary": json.dumps(boundary),
                "evidence": json.dumps(evidence_payload),
                "reviewed_by": reviewed_by,
            },
        )
        review_id = int(cur.fetchone()["id"])
        cur.execute(
            """
            UPDATE employer_origin_source_candidates
            SET candidate_url = %s,
                updated_at = now()
            WHERE id = %s
              AND company_key = %s
              AND status = %s
              AND (candidate_url IS NULL OR btrim(candidate_url) = '')
            """,
            (
                item.selected_url,
                item.candidate_id,
                item.company_key,
                item.candidate_status,
            ),
        )
        if cur.rowcount != 1:
            raise SystemExit(
                "Candidate URL write did not update exactly the locked target row for "
                f"{item.candidate_id}:{item.company_key}; transaction will abort."
            )
    return review_id


def origin_args_from_cli(args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        target_location=args.target_location,
        target_locale=args.target_locale,
        reviewed_by=args.reviewed_by,
        timeout_seconds=args.timeout_seconds,
        max_candidates=args.max_url_candidates,
        max_url_candidates=args.max_url_candidates,
        market_evidence_limit=args.market_evidence_limit,
        search_provider=args.search_provider,
        search_query_limit=args.search_query_limit,
        search_max_results=args.search_max_results,
        search_timeout_seconds=args.search_timeout_seconds,
        search_depth=args.search_depth,
        search_results_json=args.search_results_json,
        no_probe=args.no_probe,
        max_evidence_candidates=args.max_evidence_candidates,
        max_evidence_http_requests=args.max_evidence_http_requests,
        evidence_timeout_seconds=args.evidence_timeout_seconds,
        max_response_bytes=args.max_response_bytes,
        llm_model=args.llm_model,
        llm_reasoning_effort=args.llm_reasoning_effort,
        llm_max_output_tokens=args.llm_max_output_tokens,
        llm_reserved_input_tokens=args.llm_reserved_input_tokens,
        llm_timeout_seconds=args.llm_timeout_seconds,
        max_estimated_llm_cost_usd_per_company=(
            args.max_estimated_llm_cost_usd_per_company
        ),
        disable_tavily=args.disable_tavily,
        disable_llm=args.disable_llm,
    )


def _exact_candidate_id_for_company(
    args: argparse.Namespace,
    company_key: str,
) -> int | None:
    exact_map = getattr(args, "candidate_id_by_company_key", None)
    if exact_map is None:
        return None
    if company_key not in exact_map:
        raise SystemExit(
            "Exact candidate identity map is present but missing company_key="
            f"{company_key!r}; refusing company-key-only fallback."
        )
    return int(exact_map[company_key])


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    origin_args = origin_args_from_cli(args)
    items = []

    with connect() as conn:
        for company_key in args.company_key:
            exact_candidate_id = _exact_candidate_id_for_company(args, company_key)
            candidate = load_candidate(
                conn,
                company_key,
                candidate_id=exact_candidate_id,
            )
            if args.single_pass_diagnostic:
                payload = run_atomic_origin_discovery(origin_args, company_key)
            else:
                payload = run_default_repair_for_company(origin_args, company_key)
            evidence = evidence_from_origin_discovery_payload(payload)
            duplicate_exists = duplicate_selected_url_exists(
                conn,
                candidate=candidate,
                selected_url=evidence.selected_url,
            )
            planned = build_persistence_plan_item(
                candidate,
                evidence,
                include_active_controlled=args.include_active_controlled,
                duplicate_selected_url_exists=duplicate_exists,
            )
            if args.apply and planned.apply_allowed:
                review_id = write_review_and_candidate_url(
                    conn,
                    item=planned,
                    evidence=evidence,
                    reviewed_by=args.reviewed_by,
                )
                planned = build_persistence_plan_item(
                    candidate,
                    evidence,
                    include_active_controlled=args.include_active_controlled,
                    duplicate_selected_url_exists=duplicate_exists,
                    applied=True,
                    audit_review_id=review_id,
                )
                print(
                    "candidate_url_applied: "
                    f"company_key={company_key} "
                    f"url={planned.selected_url} "
                    f"review_id={review_id}"
                )
            else:
                repair = payload.get("default_repair")
                repair_state = (
                    repair.get("final_state")
                    if isinstance(repair, dict)
                    else "single_pass_diagnostic"
                )
                print(
                    "candidate_url_plan: "
                    f"company_key={company_key} "
                    f"decision={planned.decision} "
                    f"status={planned.review_status} "
                    f"selected_url={planned.selected_url or '<none>'} "
                    f"apply_allowed={planned.apply_allowed} "
                    f"repair_state={repair_state}"
                )
            items.append(planned)
        if args.apply:
            conn.commit()
        else:
            conn.rollback()

    payload = report_payload(
        benchmark_label=args.benchmark_label,
        items=items,
    )
    payload["default_repair_enabled"] = not args.single_pass_diagnostic
    json_path = args.output_json or output_dir / f"{args.benchmark_label}.json"
    md_path = args.output_markdown or output_dir / f"{args.benchmark_label}.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    md_path.write_text(markdown_report(payload), encoding="utf-8")
    print("json_report_written: " + str(json_path))
    print("markdown_report_written: " + str(md_path))
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "CAND-001 reviewed candidate_url persistence after mandatory default "
            "URL repair."
        )
    )
    parser.add_argument("--benchmark-label", required=True)
    parser.add_argument("--company-key", action="append", required=True)
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--target-locale", default="de")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist an A/B-tier selected URL. Default is dry-run.",
    )
    parser.add_argument("--include-active-controlled", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--max-url-candidates", type=int, default=12)
    parser.add_argument("--market-evidence-limit", type=int, default=30)
    parser.add_argument(
        "--search-provider",
        action="append",
        default=["none"],
        choices=("none", "tavily"),
        help="Compatibility option for --single-pass-diagnostic only.",
    )
    parser.add_argument("--search-query-limit", type=int, default=4)
    parser.add_argument("--search-max-results", type=int, default=5)
    parser.add_argument("--search-timeout-seconds", type=float, default=8.0)
    parser.add_argument(
        "--search-depth",
        choices=("basic", "advanced"),
        default="advanced",
    )
    parser.add_argument("--search-results-json")
    parser.add_argument("--max-evidence-candidates", type=int, default=4)
    parser.add_argument("--max-evidence-http-requests", type=int, default=12)
    parser.add_argument("--evidence-timeout-seconds", type=float, default=8.0)
    parser.add_argument("--max-response-bytes", type=int, default=750_000)
    parser.add_argument(
        "--llm-model",
        default=os.getenv("ORIGIN_ADJUDICATION_MODEL", "gpt-5.4-mini"),
    )
    parser.add_argument("--llm-reasoning-effort", default="low")
    parser.add_argument("--llm-max-output-tokens", type=int, default=600)
    parser.add_argument("--llm-reserved-input-tokens", type=int, default=5000)
    parser.add_argument("--llm-timeout-seconds", type=float, default=60.0)
    parser.add_argument(
        "--max-estimated-llm-cost-usd-per-company",
        type=float,
        default=0.01,
    )
    parser.add_argument("--disable-tavily", action="store_true")
    parser.add_argument("--disable-llm", action="store_true")
    parser.add_argument(
        "--single-pass-diagnostic",
        action="store_true",
        help="Explicit legacy diagnostic path; cannot be used with --apply.",
    )
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="Only valid with --single-pass-diagnostic and never with --apply.",
    )
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    return parser


def main() -> None:
    load_local_env_file()
    args = build_parser().parse_args()
    if args.apply and args.single_pass_diagnostic:
        raise SystemExit(
            "CAND-001 --apply requires the mandatory default repair path."
        )
    if args.no_probe and not args.single_pass_diagnostic:
        raise SystemExit("--no-probe is only valid with --single-pass-diagnostic")
    if args.apply and args.no_probe:
        raise SystemExit(
            "CAND-001 --apply requires HTTP probing; remove --no-probe."
        )
    if len(args.search_provider) > 1 and "none" in args.search_provider:
        args.search_provider = [
            provider for provider in args.search_provider if provider != "none"
        ]
    run(args)


if __name__ == "__main__":
    main()
