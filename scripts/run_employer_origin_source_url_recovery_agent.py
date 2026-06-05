"""Recover a public employer-origin source URL for a blocked candidate.

Boundary: this agent only probes a small deterministic set of company-related
career/job URL candidates and may update employer_origin_source_candidates.
It does not build/register connectors, activate sources, write Bronze records,
change scheduler configuration or bypass later approval gates.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row
import requests

from src.config import get_database_config
from src.search_intelligence.origin_url_recovery import (
    RecoveryProbeResult,
    generate_recovery_url_candidates,
    probe_result_from_http_response,
    select_recovery_url,
)

BOUNDARY = {
    "no_connector_artifact_generation": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "no_bronze_write": True,
    "no_scheduler_change": True,
    "bounded_recovery_probe": True,
}


@dataclass(frozen=True)
class Candidate:
    candidate_id: int
    company_key: str
    company_name: str
    candidate_url: str
    source_name_candidate: str
    source_family_candidate: str
    source_target_candidate: str | None
    source_type_candidate: str


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def load_candidate(conn: psycopg.Connection[Any], company_key: str) -> Candidate:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                company_key,
                company_name,
                candidate_url,
                source_name_candidate,
                source_family_candidate,
                source_target_candidate,
                source_type_candidate
            FROM employer_origin_source_candidates
            WHERE company_key = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (company_key,),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"No employer-origin source candidate found for company_key={company_key!r}.")
    return Candidate(
        candidate_id=int(row["id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        candidate_url=str(row["candidate_url"]),
        source_name_candidate=str(row["source_name_candidate"]),
        source_family_candidate=str(row["source_family_candidate"]),
        source_target_candidate=row["source_target_candidate"],
        source_type_candidate=str(row["source_type_candidate"]),
    )


def http_probe(url: str, *, timeout_seconds: float) -> RecoveryProbeResult:
    try:
        response = requests.get(
            url,
            timeout=timeout_seconds,
            headers={
                "User-Agent": "job-application-pipeline-origin-url-recovery/0.1 (+bounded personal portfolio project)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        return RecoveryProbeResult(
            url=url,
            final_url=None,
            status_code=None,
            accepted=False,
            reason=f"request failed: {exc.__class__.__name__}",
        )
    return probe_result_from_http_response(url, response)


def reset_downstream_gate_state(
    conn: psycopg.Connection[Any],
    *,
    candidate_id: int,
    reviewed_by: str,
    selected_url: str,
    previous_url: str,
    probe_results: tuple[RecoveryProbeResult, ...],
) -> None:
    evidence = {
        "recovery_agent": "run_employer_origin_source_url_recovery_agent",
        "decision": "candidate_url_recovered",
        "previous_candidate_url": previous_url,
        "selected_candidate_url": selected_url,
        "boundary": BOUNDARY,
        "probe_results": [asdict(result) for result in probe_results],
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE employer_origin_source_candidates
            SET candidate_url = %s::text,
                status = 'discovery',
                risk_level = 'unknown',
                notes = concat_ws(
                    ' ',
                    nullif(notes, ''),
                    %s::text
                ),
                updated_at = now()
            WHERE id = %s::bigint
            """,
            (
                selected_url,
                f"Source URL recovered by bounded A1f recovery agent; reviewed_by={reviewed_by}.",
                candidate_id,
            ),
        )
        cur.execute(
            """
            UPDATE employer_origin_candidate_gate_reviews
            SET gate_status = 'not_started',
                decision = 'defer',
                stop_reason = NULL,
                evidence = %s::jsonb,
                reviewed_at = now(),
                reviewed_by = %s,
                updated_at = now()
            WHERE candidate_id = %s::bigint
              AND gate_order >= 4
            """,
            (json.dumps(evidence, sort_keys=True), reviewed_by, candidate_id),
        )
        cur.execute(
            """
            INSERT INTO employer_origin_candidate_gate_events (
                candidate_id,
                event_type,
                new_state,
                event_reason,
                created_by
            )
            VALUES (%s, 'candidate_url_recovered', %s::jsonb, %s, %s)
            """,
            (
                candidate_id,
                json.dumps(evidence, sort_keys=True),
                "bounded source URL recovery selected a reachable company-related career/job URL",
                reviewed_by,
            ),
        )
    conn.commit()


def record_unresolved_recovery(
    conn: psycopg.Connection[Any],
    *,
    candidate_id: int,
    reviewed_by: str,
    previous_url: str,
    probe_results: tuple[RecoveryProbeResult, ...],
) -> None:
    evidence = {
        "recovery_agent": "run_employer_origin_source_url_recovery_agent",
        "decision": "no_reachable_recovery_url_found",
        "previous_candidate_url": previous_url,
        "boundary": BOUNDARY,
        "probe_results": [asdict(result) for result in probe_results],
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE employer_origin_candidate_gate_reviews
            SET gate_status = 'manual_review_required',
                decision = 'manual_review_required',
                stop_reason = 'bounded source URL recovery found no reachable company-related career/job URL',
                evidence = %s::jsonb,
                reviewed_at = now(),
                reviewed_by = %s,
                updated_at = now()
            WHERE candidate_id = %s::bigint
              AND gate_name = 'technical_reachability_gate'
            """,
            (json.dumps(evidence, sort_keys=True), reviewed_by, candidate_id),
        )
    conn.commit()


def gate_review_args(candidate: Candidate, *, candidate_url: str, target_location: str, reviewed_by: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "scripts.run_employer_origin_gate_agent",
        "--company-key",
        candidate.company_key,
        "--company-name",
        candidate.company_name,
        "--candidate-url",
        candidate_url,
        "--source-name-candidate",
        candidate.source_name_candidate,
        "--source-family-candidate",
        candidate.source_family_candidate,
        "--source-target-candidate",
        candidate.source_target_candidate or target_location,
        "--source-type-candidate",
        candidate.source_type_candidate,
        "--target-location",
        target_location,
        "--reviewed-by",
        reviewed_by,
    ]


def run_gate_review_after_recovery(candidate: Candidate, *, selected_url: str, target_location: str, reviewed_by: str) -> int:
    command = gate_review_args(candidate, candidate_url=selected_url, target_location=target_location, reviewed_by=reviewed_by)
    print("running_recovered_gate_review:", " ".join(command))
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return int(completed.returncode)


def run(args: argparse.Namespace) -> int:
    with connect() as conn:
        candidate = load_candidate(conn, args.company_key)
        candidates = generate_recovery_url_candidates(
            company_key=candidate.company_key,
            company_name=candidate.company_name,
            source_family_candidate=candidate.source_family_candidate,
            current_url=candidate.candidate_url,
            max_candidates=args.max_candidates,
        )
        selected_url, probe_results = select_recovery_url(
            candidates,
            probe=lambda url: http_probe(url, timeout_seconds=args.timeout_seconds),
        )

        print(f"candidate_id: {candidate.candidate_id}")
        print(f"company_key: {candidate.company_key}")
        print(f"previous_candidate_url: {candidate.candidate_url}")
        print(f"recovery_candidate_count: {len(candidates)}")
        for result in probe_results:
            print(f"probe: {result.url} | accepted={result.accepted} | reason={result.reason}")

        if not selected_url:
            record_unresolved_recovery(
                conn,
                candidate_id=candidate.candidate_id,
                reviewed_by=args.reviewed_by,
                previous_url=candidate.candidate_url,
                probe_results=probe_results,
            )
            print("source_url_recovery_result: manual_review_required")
            return 0

        reset_downstream_gate_state(
            conn,
            candidate_id=candidate.candidate_id,
            reviewed_by=args.reviewed_by,
            selected_url=selected_url,
            previous_url=candidate.candidate_url,
            probe_results=probe_results,
        )
        print(f"selected_recovery_url: {selected_url}")
        print("source_url_recovery_result: recovered")

    if args.run_gate_review_after_recovery:
        exit_code = run_gate_review_after_recovery(
            candidate,
            selected_url=selected_url,
            target_location=args.target_location,
            reviewed_by=args.reviewed_by,
        )
        if exit_code == 0:
            print("source_url_recovery_followup_gate_review: completed")
        else:
            print(f"source_url_recovery_followup_gate_review: failed exit_code={exit_code}", file=sys.stderr)
        return exit_code

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run bounded employer-origin source URL recovery for a blocked candidate.")
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--run-gate-review-after-recovery", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
