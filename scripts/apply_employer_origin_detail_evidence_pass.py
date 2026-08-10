from __future__ import annotations

import argparse
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_detail_evidence_repair_agent import (
    DEFAULT_PROFILE_TERMS,
    DEFAULT_SEARCH_QUERY_LIMIT,
    DEFAULT_SEARCH_RESULT_LIMIT,
    DEFAULT_LOCATION_TERMS,
    DatabaseConfig,
    GateStateRepository,
    RepairOutcome,
    SourceCandidate,
    build_repair_outcome,
    load_local_env_file,
    repair_report_lines,
    unique_ordered,
)

APPROVAL_TOKEN = "approve_employer_origin_detail_evidence_pass"
DEFAULT_EXPECTED_STATUS = "discovery"


class ReviewedPassApplyError(RuntimeError):
    pass


def validate_approval_token(value: str) -> None:
    if value != APPROVAL_TOKEN:
        raise ReviewedPassApplyError("approval_token_mismatch")


def validate_candidate_identity(
    candidate: SourceCandidate,
    *,
    expected_company_key: str,
    expected_status: str,
) -> None:
    if candidate.company_key != expected_company_key:
        raise ReviewedPassApplyError("candidate_company_key_mismatch")
    if candidate.status != expected_status:
        raise ReviewedPassApplyError("candidate_status_mismatch")


def validate_pass_outcome(outcome: RepairOutcome) -> None:
    if outcome.gate_status != "passed" or outcome.decision != "passed" or not outcome.details:
        raise ReviewedPassApplyError("fresh_detail_evidence_not_passed")


def lock_and_revalidate_candidate(
    conn: psycopg.Connection[Any],
    *,
    snapshot: SourceCandidate,
    expected_company_key: str,
    expected_status: str,
) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select id, company_key, candidate_url, status
            from employer_origin_source_candidates
            where id = %s
            for update
            """,
            (snapshot.id,),
        )
        row = cur.fetchone()

    if row is None:
        raise ReviewedPassApplyError("candidate_missing_before_write")
    if int(row["id"]) != snapshot.id:
        raise ReviewedPassApplyError("candidate_id_drift_before_write")
    if str(row["company_key"]) != expected_company_key:
        raise ReviewedPassApplyError("candidate_company_key_drift_before_write")
    if str(row["status"]) != expected_status:
        raise ReviewedPassApplyError("candidate_status_drift_before_write")
    if str(row["candidate_url"] or "") != snapshot.candidate_url:
        raise ReviewedPassApplyError("candidate_url_drift_before_write")


def build_terms(args: argparse.Namespace) -> tuple[tuple[str, ...], tuple[str, ...]]:
    profile_terms = unique_ordered([*DEFAULT_PROFILE_TERMS, *(args.profile_term or [])])
    location_terms = unique_ordered([*DEFAULT_LOCATION_TERMS, *(args.location_term or [])])
    if args.target_location:
        location_terms = unique_ordered([args.target_location, *location_terms])
    return profile_terms, location_terms


def run_apply(args: argparse.Namespace) -> int:
    validate_approval_token(args.approval_token)
    load_local_env_file()
    profile_terms, location_terms = build_terms(args)

    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        repo = GateStateRepository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=None)
        validate_candidate_identity(
            candidate,
            expected_company_key=args.expected_company_key,
            expected_status=args.expected_candidate_status,
        )
        gates = repo.load_gates(candidate.id)

        outcome = build_repair_outcome(
            candidate=candidate,
            gates=gates,
            profile_terms=profile_terms,
            location_terms=location_terms,
            max_seed_pages=args.max_seed_pages,
            max_detail_pages=args.max_detail_pages,
            enable_search_discovery=not args.disable_search_discovery,
            max_search_queries=args.max_search_queries,
            max_search_results=args.max_search_results,
            search_provider=args.search_provider,
        )

        for line in repair_report_lines(candidate, outcome):
            print(line)

        validate_pass_outcome(outcome)
        lock_and_revalidate_candidate(
            conn,
            snapshot=candidate,
            expected_company_key=args.expected_company_key,
            expected_status=args.expected_candidate_status,
        )
        repo.record_detail_evidence_gate(
            candidate_id=candidate.id,
            outcome=outcome,
            reviewed_by=args.reviewed_by,
        )
        conn.commit()

    print(
        "APPLIED: reviewed passed-only detail_evidence_gate "
        f"candidate_id={candidate.id} company_key={candidate.company_key} "
        f"supported_details={len(outcome.details)}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reviewed fail-closed persistence for an accepted employer-origin detail-evidence pass."
    )
    parser.add_argument("--candidate-id", type=int, required=True)
    parser.add_argument("--expected-company-key", required=True)
    parser.add_argument("--expected-candidate-status", default=DEFAULT_EXPECTED_STATUS)
    parser.add_argument("--approval-token", required=True)
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--profile-term", action="append")
    parser.add_argument("--location-term", action="append")
    parser.add_argument("--max-seed-pages", type=int, default=12)
    parser.add_argument("--max-detail-pages", type=int, default=8)
    parser.add_argument("--max-search-queries", type=int, default=DEFAULT_SEARCH_QUERY_LIMIT)
    parser.add_argument("--max-search-results", type=int, default=DEFAULT_SEARCH_RESULT_LIMIT)
    parser.add_argument("--search-provider", choices=("duckduckgo_html",), default="duckduckgo_html")
    parser.add_argument("--disable-search-discovery", action="store_true")
    parser.add_argument("--reviewed-by", default="agent")
    return parser


def main() -> None:
    try:
        raise SystemExit(run_apply(build_parser().parse_args()))
    except ReviewedPassApplyError as exc:
        print(f"STOP: {exc}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
