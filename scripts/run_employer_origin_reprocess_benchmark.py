"""Benchmark employer-origin candidate reprocessing after learning improvements.

The script is intentionally conservative: it snapshots before/after state,
resets candidates only with --apply and can rerun next-safe actions with loop
protection. It is meant to measure pipeline delta, not to hide mutations in
local exports or manual spreadsheets.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.employer_origin_gate_registry import OFFICIAL_EMPLOYER_ORIGIN_GATES

IN_PROCESS_STATUSES = (
    "discovery",
    "manual_review_required",
    "connector_candidate",
    "build_approval_required",
    "registration_approval_required",
    "connector_validation_required",
)


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def candidate_filter_sql(*, include_active_controlled: bool) -> str:
    statuses = list(IN_PROCESS_STATUSES)
    if include_active_controlled:
        statuses.append("active_controlled")
    quoted = ", ".join("'" + status + "'" for status in statuses)
    active_controlled_history_guard = (
        "TRUE" if include_active_controlled else "c.status <> 'active_controlled'"
    )
    return f"""
        c.status IN ({quoted})
        OR (
            {active_controlled_history_guard}
            AND EXISTS (
                SELECT 1
                FROM employer_origin_candidate_gate_reviews gr
                WHERE gr.candidate_id = c.id
                  AND COALESCE(gr.gate_status, '') NOT IN ('not_started', 'defer')
            )
        )
    """


def normalize_company_keys(company_keys: list[str] | None) -> list[str]:
    """Return unique, non-empty company keys in caller-specified guest-list order."""

    normalized: list[str] = []
    for raw_key in company_keys or []:
        key = str(raw_key or "").strip()
        if key and key not in normalized:
            normalized.append(key)
    return normalized


def load_candidate_keys(
    conn: psycopg.Connection[Any],
    *,
    include_active_controlled: bool,
    limit: int,
    company_keys: list[str] | None = None,
) -> list[tuple[int, str, str]]:
    guest_list = normalize_company_keys(company_keys)
    with conn.cursor() as cur:
        if guest_list:
            active_controlled_guard = "TRUE" if include_active_controlled else "c.status <> 'active_controlled'"
            cur.execute(
                f"""
                SELECT c.id, c.company_key, c.status
                FROM employer_origin_source_candidates c
                WHERE c.company_key = ANY(%s::text[])
                  AND {active_controlled_guard}
                ORDER BY array_position(%s::text[], c.company_key), c.updated_at DESC NULLS LAST, c.id DESC
                LIMIT %s
                """,
                (guest_list, guest_list, limit),
            )
        else:
            where_clause = candidate_filter_sql(include_active_controlled=include_active_controlled)
            cur.execute(
                f"""
                SELECT c.id, c.company_key, c.status
                FROM employer_origin_source_candidates c
                WHERE {where_clause}
                ORDER BY c.updated_at DESC NULLS LAST, c.id
                LIMIT %s
                """,
                (limit,),
            )
        rows = cur.fetchall()
    return [(int(row["id"]), str(row["company_key"]), str(row["status"])) for row in rows]


def load_duplicate_candidate_identities(
    conn: psycopg.Connection[Any],
    *,
    candidate_ids: list[int],
) -> list[dict[str, Any]]:
    """Return exact identity duplicates for the selected candidate identities.

    This is intentionally a preflight guard, not a DB constraint. A company may
    legitimately have more than one source target later. For reprocess safety we
    only stop when the exact source identity currently selected for reprocessing
    exists more than once.
    """
    if not candidate_ids:
        return []

    with conn.cursor() as cur:
        cur.execute(
            """
            WITH selected_identities AS (
                SELECT DISTINCT company_key, source_name_candidate
                FROM employer_origin_source_candidates
                WHERE id = ANY(%s::bigint[])
            )
            SELECT
                c.company_key,
                c.source_name_candidate,
                array_agg(c.id ORDER BY c.id) AS candidate_ids,
                array_agg(c.status ORDER BY c.id) AS statuses,
                array_agg(
                    COALESCE(NULLIF(btrim(c.candidate_url), ''), '<empty>')
                    ORDER BY c.id
                ) AS candidate_urls,
                COUNT(*) AS duplicate_count
            FROM employer_origin_source_candidates c
            JOIN selected_identities selected
              ON selected.company_key = c.company_key
             AND selected.source_name_candidate IS NOT DISTINCT FROM c.source_name_candidate
            GROUP BY c.company_key, c.source_name_candidate
            HAVING COUNT(*) > 1
            ORDER BY c.company_key, c.source_name_candidate NULLS FIRST
            """,
            (candidate_ids,),
        )
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def print_duplicate_candidate_preflight(duplicates: list[dict[str, Any]], *, apply: bool) -> bool:
    """Print duplicate diagnostics and return True when apply must abort."""
    if not duplicates:
        return False

    print("candidate_identity_duplicates_detected:")
    for duplicate in duplicates:
        print(
            "duplicate_candidate_identity: "
            f"company_key={duplicate['company_key']} "
            f"source_name_candidate={duplicate['source_name_candidate']} "
            f"candidate_ids={list(duplicate['candidate_ids'])} "
            f"statuses={list(duplicate['statuses'])} "
            f"candidate_urls={list(duplicate['candidate_urls'])}"
        )

    if apply:
        print("ABORT: duplicate candidate identity detected; cleanup or merge candidates before --apply")
        return True

    print("dry_run warning: duplicate candidate identities exist; --apply would abort until they are reviewed")
    return False


def snapshot(
    conn: psycopg.Connection[Any],
    *,
    benchmark_label: str,
    phase: str,
    include_active_controlled: bool,
    limit: int,
    candidates: list[tuple[int, str, str]] | None = None,
) -> int:
    candidate_ids = [candidate_id for candidate_id, _, _ in candidates or []]
    where_clause = "c.id = ANY(%s::bigint[])" if candidate_ids else candidate_filter_sql(include_active_controlled=include_active_controlled)
    query_params: tuple[object, ...] = (candidate_ids,) if candidate_ids else ()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO employer_origin_reprocess_benchmarks (
                benchmark_label,
                phase,
                candidate_id,
                company_key,
                company_name,
                candidate_status,
                current_stage,
                passed_gate_count,
                blocked_gate_count,
                total_gate_count,
                blocking_gate,
                blocking_decision,
                blocker_reason,
                job_detail_evidence_count,
                learned_signal_count,
                action_run_count,
                evidence
            )
            SELECT
                %s AS benchmark_label,
                %s AS phase,
                c.id AS candidate_id,
                c.company_key,
                c.company_name,
                c.status AS candidate_status,
                lifecycle.current_stage,
                lifecycle.passed_gate_count,
                lifecycle.blocked_gate_count,
                lifecycle.total_gate_count,
                lifecycle.blocking_gate,
                lifecycle.blocking_decision,
                lifecycle.blocker_reason,
                COALESCE(detail_counts.detail_count, 0) AS job_detail_evidence_count,
                COALESCE(signal_counts.signal_count, 0) AS learned_signal_count,
                COALESCE(action_counts.action_count, 0) AS action_run_count,
                jsonb_build_object(
                    'learning_input_only', true,
                    'include_active_controlled', %s,
                    'benchmark_boundary', jsonb_build_object(
                        'no_csv_or_export_input', true,
                        'snapshot_only', true,
                        'guest_list_candidate_ids', to_jsonb(%s::bigint[])
                    )
                ) AS evidence
            FROM employer_origin_source_candidates c
            LEFT JOIN gold_candidate_lifecycle_status lifecycle
              ON lifecycle.candidate_id = c.id
            LEFT JOIN (
                SELECT candidate_id, count(*) AS detail_count
                FROM employer_origin_job_detail_evidence
                GROUP BY candidate_id
            ) detail_counts ON detail_counts.candidate_id = c.id
            LEFT JOIN (
                SELECT first_seen_candidate_id AS candidate_id, count(*) AS signal_count
                FROM employer_origin_learned_relevance_signals
                GROUP BY first_seen_candidate_id
            ) signal_counts ON signal_counts.candidate_id = c.id
            LEFT JOIN (
                SELECT candidate_id, count(*) AS action_count
                FROM search_intelligence_action_runs
                GROUP BY candidate_id
            ) action_counts ON action_counts.candidate_id = c.id
            WHERE {where_clause}
            ORDER BY c.updated_at DESC NULLS LAST, c.id
            LIMIT %s
            """,
            (benchmark_label, phase, include_active_controlled, candidate_ids, *query_params, limit),
        )
        inserted = cur.rowcount
    conn.commit()
    return int(inserted)


def reset_candidates(
    conn: psycopg.Connection[Any],
    *,
    candidates: list[tuple[int, str, str]],
    reviewed_by: str,
    apply: bool,
) -> None:
    if not candidates:
        print("reset_candidates: no candidates selected")
        return
    ids = [candidate_id for candidate_id, _, _ in candidates]
    print("reset_candidates_selected:", ", ".join(f"{key}({status})" for _, key, status in candidates))
    if not apply:
        print("dry_run: no candidate or gate rows were changed; pass --apply to reset")
        return

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE employer_origin_source_candidates
            SET status = 'discovery',
                notes = concat_ws(' ', nullif(notes, ''), %s::text),
                updated_at = now()
            WHERE id = ANY(%s)
            """,
            (f"Reprocess benchmark reset requested; reviewed_by={reviewed_by}.", ids),
        )
        for gate in OFFICIAL_EMPLOYER_ORIGIN_GATES:
            cur.execute(
                """
                INSERT INTO employer_origin_candidate_gate_reviews (
                    candidate_id,
                    gate_name,
                    gate_order,
                    gate_status,
                    decision,
                    is_hard_gate,
                    stop_reason,
                    evidence,
                    reviewed_at,
                    reviewed_by,
                    updated_at
                )
                SELECT
                    candidate_id,
                    %s,
                    %s,
                    'not_started',
                    'defer',
                    %s,
                    NULL,
                    jsonb_build_object(
                        'decision', 'reprocess_benchmark_reset',
                        'learning_input_only', true,
                        'no_gate_pass', true,
                        'reviewed_by', %s
                    ),
                    now(),
                    %s,
                    now()
                FROM unnest(%s::bigint[]) AS selected(candidate_id)
                ON CONFLICT (candidate_id, gate_name)
                DO UPDATE SET
                    gate_status = EXCLUDED.gate_status,
                    decision = EXCLUDED.decision,
                    stop_reason = EXCLUDED.stop_reason,
                    evidence = EXCLUDED.evidence,
                    reviewed_at = EXCLUDED.reviewed_at,
                    reviewed_by = EXCLUDED.reviewed_by,
                    updated_at = now()
                """,
                (gate.gate_name, gate.gate_order, gate.is_hard_gate, reviewed_by, reviewed_by, ids),
            )
    conn.commit()
    print(f"reset_candidates_applied: {len(ids)}")


def run_next_safe_for_candidates(
    *,
    candidates: list[tuple[int, str, str]],
    target_location: str,
    reviewed_by: str,
    max_iterations: int,
    apply: bool,
) -> None:
    if not candidates:
        print("run_next_safe_actions: no candidates selected")
        return
    if not apply:
        print("dry_run next-safe plan:")
        for _, company_key, _ in candidates:
            print(
                " ".join(
                    [
                        sys.executable,
                        "-m",
                        "scripts.run_employer_origin_next_safe_action_agent",
                        "--company-key",
                        company_key,
                        "--target-location",
                        target_location,
                        "--reviewed-by",
                        reviewed_by,
                        "--plan-only",
                    ]
                )
            )
        print("pass --apply to execute next-safe actions")
        return

    for _, company_key, _ in candidates:
        last_action: str | None = None
        repeated = 0
        for iteration in range(1, max_iterations + 1):
            command = [
                sys.executable,
                "-m",
                "scripts.run_employer_origin_next_safe_action_agent",
                "--company-key",
                company_key,
                "--target-location",
                target_location,
                "--reviewed-by",
                reviewed_by,
            ]
            completed = subprocess.run(command, check=False, capture_output=True, text=True)
            print(f"=== {company_key} iteration {iteration} exit={completed.returncode} ===")
            if completed.stdout:
                print(completed.stdout, end="")
            if completed.stderr:
                print(completed.stderr, end="", file=sys.stderr)
            action = ""
            for line in completed.stdout.splitlines():
                if line.startswith("next_safe_action:"):
                    action = line.split(":", 1)[1].strip()
            if completed.returncode != 0:
                break
            if not action or action in {"no_safe_automated_action", "monitor_existing_controlled_source"}:
                break
            repeated = repeated + 1 if action == last_action else 0
            last_action = action
            if repeated >= 1:
                print(f"loop_guard: stopping {company_key} after repeated action {action!r}")
                break


def print_delta(conn: psycopg.Connection[Any], *, benchmark_label: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH before_rows AS (
                SELECT * FROM employer_origin_reprocess_benchmarks
                WHERE benchmark_label = %s AND phase = 'before'
            ), after_rows AS (
                SELECT * FROM employer_origin_reprocess_benchmarks
                WHERE benchmark_label = %s AND phase = 'after'
            )
            SELECT
                COALESCE(a.company_key, b.company_key) AS company_key,
                b.candidate_status AS before_status,
                a.candidate_status AS after_status,
                b.passed_gate_count AS before_passed,
                a.passed_gate_count AS after_passed,
                COALESCE(a.passed_gate_count, 0) - COALESCE(b.passed_gate_count, 0) AS passed_delta,
                b.blocking_gate AS before_blocker,
                a.blocking_gate AS after_blocker,
                COALESCE(a.job_detail_evidence_count, 0) - COALESCE(b.job_detail_evidence_count, 0) AS detail_evidence_delta,
                COALESCE(a.learned_signal_count, 0) - COALESCE(b.learned_signal_count, 0) AS learned_signal_delta,
                COALESCE(a.action_run_count, 0) - COALESCE(b.action_run_count, 0) AS action_run_delta
            FROM before_rows b
            FULL OUTER JOIN after_rows a
              ON a.candidate_id = b.candidate_id
            ORDER BY passed_delta DESC, detail_evidence_delta DESC, company_key
            """,
            (benchmark_label, benchmark_label),
        )
        rows = cur.fetchall()
    print("=== benchmark delta ===")
    for row in rows:
        print(
            f"{row['company_key']}: gates {row['before_passed']} -> {row['after_passed']} "
            f"(delta={row['passed_delta']}), blocker {row['before_blocker']} -> {row['after_blocker']}, "
            f"detail_evidence_delta={row['detail_evidence_delta']}, learned_signal_delta={row['learned_signal_delta']}, "
            f"action_run_delta={row['action_run_delta']}"
        )


def run(args: argparse.Namespace) -> int:
    with connect() as conn:
        candidates = load_candidate_keys(
            conn,
            include_active_controlled=args.include_active_controlled,
            limit=args.max_candidates,
            company_keys=args.company_key,
        )
        if args.company_key:
            found_keys = {company_key for _, company_key, _ in candidates}
            missing_keys = [key for key in normalize_company_keys(args.company_key) if key not in found_keys]
            if missing_keys:
                print(
                    "guest_list_missing_or_protected: " + ", ".join(missing_keys)
                    + " (not found, over limit, or active_controlled without --include-active-controlled)"
                )
        duplicates = load_duplicate_candidate_identities(
            conn,
            candidate_ids=[candidate_id for candidate_id, _, _ in candidates],
        )
        duplicate_warning_blocks_mutating_dry_run = bool(duplicates) and not args.apply
        if print_duplicate_candidate_preflight(duplicates, apply=args.apply):
            return 2

        if args.snapshot_before:
            inserted = snapshot(
                conn,
                benchmark_label=args.benchmark_label,
                phase="before",
                include_active_controlled=args.include_active_controlled,
                limit=args.max_candidates,
                candidates=candidates,
            )
            print(f"snapshot_before_rows: {inserted}")
        if args.reset_candidates:
            if duplicate_warning_blocks_mutating_dry_run:
                print("dry_run: reset plan suppressed because duplicate candidate identities exist")
            else:
                reset_candidates(conn, candidates=candidates, reviewed_by=args.reviewed_by, apply=args.apply)

    if args.run_next_safe_actions:
        if duplicate_warning_blocks_mutating_dry_run:
            print("dry_run next-safe plan suppressed: duplicate candidate identities must be reviewed before --apply")
        else:
            run_next_safe_for_candidates(
                candidates=candidates,
                target_location=args.target_location,
                reviewed_by=args.reviewed_by,
                max_iterations=args.max_iterations,
                apply=args.apply,
            )

    with connect() as conn:
        if args.snapshot_after:
            inserted = snapshot(
                conn,
                benchmark_label=args.benchmark_label,
                phase="after",
                include_active_controlled=args.include_active_controlled,
                limit=args.max_candidates,
                candidates=candidates,
            )
            print(f"snapshot_after_rows: {inserted}")
        if args.compare:
            print_delta(conn, benchmark_label=args.benchmark_label)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark candidate reprocessing after learning-pipeline changes.")
    parser.add_argument("--benchmark-label", required=True)
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--max-candidates", type=int, default=50)
    parser.add_argument(
        "--company-key",
        action="append",
        help="Explicit guest-list company key to reprocess. Repeat for multiple candidates. Active-controlled rows still require --include-active-controlled.",
    )
    parser.add_argument("--max-iterations", type=int, default=6)
    parser.add_argument("--include-active-controlled", action="store_true")
    parser.add_argument("--snapshot-before", action="store_true")
    parser.add_argument("--snapshot-after", action="store_true")
    parser.add_argument("--reset-candidates", action="store_true")
    parser.add_argument("--run-next-safe-actions", action="store_true")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Actually reset candidates or execute next-safe actions. Without this flag, mutating steps are dry-run only.")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
