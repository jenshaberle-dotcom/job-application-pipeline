"""Audit and clean duplicate employer-origin candidate artifacts.

SI-015 is intentionally conservative. It supports reviewed cleanup of exact
candidate-identity duplicates such as a bug-created row with a literal "None"
URL. It does not silently merge candidates and it does not infer whether two
legitimate source targets should be consolidated.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any

from src.config import get_database_config

NONE_LIKE_URLS = {"", "none", "null", "<empty>"}
PROTECTED_STATUSES = {"active_controlled"}


@dataclass(frozen=True)
class CleanupCandidate:
    id: int
    company_key: str
    company_name: str
    candidate_url: str | None
    source_name_candidate: str
    source_family_candidate: str
    source_target_candidate: str | None
    source_type_candidate: str
    status: str
    risk_level: str
    notes: str | None


def connect() -> Any:
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def normalize_candidate_url(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if normalized.lower() in NONE_LIKE_URLS:
        return None
    return normalized


def candidate_from_row(row: dict[str, Any]) -> CleanupCandidate:
    return CleanupCandidate(
        id=int(row["id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        candidate_url=normalize_candidate_url(row.get("candidate_url")),
        source_name_candidate=str(row["source_name_candidate"]),
        source_family_candidate=str(row["source_family_candidate"]),
        source_target_candidate=(
            None if row.get("source_target_candidate") is None else str(row["source_target_candidate"])
        ),
        source_type_candidate=str(row["source_type_candidate"]),
        status=str(row["status"]),
        risk_level=str(row["risk_level"]),
        notes=None if row.get("notes") is None else str(row["notes"]),
    )


def candidate_snapshot(candidate: CleanupCandidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "company_key": candidate.company_key,
        "company_name": candidate.company_name,
        "candidate_url": candidate.candidate_url,
        "source_name_candidate": candidate.source_name_candidate,
        "source_family_candidate": candidate.source_family_candidate,
        "source_target_candidate": candidate.source_target_candidate,
        "source_type_candidate": candidate.source_type_candidate,
        "status": candidate.status,
        "risk_level": candidate.risk_level,
        "notes": candidate.notes,
    }


def find_duplicate_identities(
    conn: Any,
    *,
    company_key: str | None = None,
    source_name_candidate: str | None = None,
) -> list[dict[str, Any]]:
    filters = []
    params: list[Any] = []
    if company_key:
        filters.append("company_key = %s")
        params.append(company_key)
    if source_name_candidate:
        filters.append("source_name_candidate = %s")
        params.append(source_name_candidate)
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                company_key,
                source_name_candidate,
                array_agg(id ORDER BY id) AS candidate_ids,
                array_agg(status ORDER BY id) AS statuses,
                array_agg(
                    CASE
                        WHEN candidate_url IS NULL OR btrim(candidate_url) = '' THEN '<empty>'
                        ELSE candidate_url
                    END
                    ORDER BY id
                ) AS candidate_urls,
                count(*) AS duplicate_count
            FROM employer_origin_source_candidates
            {where_clause}
            GROUP BY company_key, source_name_candidate
            HAVING count(*) > 1
            ORDER BY company_key, source_name_candidate
            """,
            params,
        )
        return [dict(row) for row in cur.fetchall()]


def load_candidate(conn: Any, candidate_id: int) -> CleanupCandidate:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM employer_origin_source_candidates
            WHERE id = %s
            """,
            (candidate_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"candidate_id not found: {candidate_id}")
    return candidate_from_row(dict(row))


def load_gate_reviews(conn: Any, candidate_id: int) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                gate_name,
                gate_order,
                gate_status,
                decision,
                is_hard_gate,
                stop_reason,
                evidence,
                reviewed_at,
                reviewed_by,
                created_at,
                updated_at
            FROM employer_origin_candidate_gate_reviews
            WHERE candidate_id = %s
            ORDER BY gate_order, gate_name
            """,
            (candidate_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def count_candidate_references(conn: Any, candidate_id: int) -> dict[str, int]:
    reference_tables = (
        "employer_origin_candidate_gate_reviews",
        "employer_origin_candidate_gate_events",
        "employer_origin_job_detail_evidence",
        "search_intelligence_action_runs",
        "employer_origin_reprocess_benchmarks",
    )
    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        for table_name in reference_tables:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                      AND column_name = 'candidate_id'
                ) AS has_candidate_id
                """,
                (table_name,),
            )
            if not bool(cur.fetchone()["has_candidate_id"]):
                counts[table_name] = 0
                continue
            cur.execute(f"SELECT count(*) AS count FROM {table_name} WHERE candidate_id = %s", (candidate_id,))
            counts[table_name] = int(cur.fetchone()["count"])
    return counts


def validate_cleanup_pair(*, keep: CleanupCandidate, duplicate: CleanupCandidate) -> list[str]:
    errors: list[str] = []
    if keep.id == duplicate.id:
        errors.append("keep and duplicate candidate IDs must differ")
    if keep.company_key != duplicate.company_key:
        errors.append("candidate company_key values differ")
    if keep.source_name_candidate != duplicate.source_name_candidate:
        errors.append("candidate source_name_candidate values differ")
    if duplicate.status in PROTECTED_STATUSES:
        errors.append(f"duplicate candidate has protected status: {duplicate.status}")
    if normalize_candidate_url(duplicate.candidate_url) is not None:
        errors.append("duplicate candidate has a usable candidate_url; cleanup requires manual design review")
    return errors


def print_duplicate_report(duplicates: list[dict[str, Any]]) -> None:
    if not duplicates:
        print("duplicate_candidate_identities: none")
        return
    print("duplicate_candidate_identities_detected:")
    for duplicate in duplicates:
        print(
            "duplicate_candidate_identity: "
            f"company_key={duplicate['company_key']} "
            f"source_name_candidate={duplicate['source_name_candidate']} "
            f"candidate_ids={list(duplicate['candidate_ids'])} "
            f"statuses={list(duplicate['statuses'])} "
            f"candidate_urls={list(duplicate['candidate_urls'])}"
        )


def build_cleanup_evidence(
    *,
    keep: CleanupCandidate,
    duplicate: CleanupCandidate,
    duplicate_gate_reviews: list[dict[str, Any]],
    duplicate_reference_counts: dict[str, int],
) -> dict[str, Any]:
    return {
        "boundary": {
            "audited_cleanup": True,
            "no_silent_delete": True,
            "no_connector_activation": True,
            "no_bronze_or_silver_write": True,
            "exact_identity_only": True,
        },
        "kept_candidate": candidate_snapshot(keep),
        "removed_candidate": candidate_snapshot(duplicate),
        "removed_candidate_gate_reviews": duplicate_gate_reviews,
        "removed_candidate_reference_counts": duplicate_reference_counts,
    }


def run_targeted_cleanup(args: argparse.Namespace) -> int:
    with connect() as conn:
        keep = load_candidate(conn, int(args.keep_candidate_id))
        duplicate = load_candidate(conn, int(args.duplicate_candidate_id))
        errors = validate_cleanup_pair(keep=keep, duplicate=duplicate)
        duplicate_gate_reviews = load_gate_reviews(conn, duplicate.id)
        duplicate_reference_counts = count_candidate_references(conn, duplicate.id)
        evidence = build_cleanup_evidence(
            keep=keep,
            duplicate=duplicate,
            duplicate_gate_reviews=duplicate_gate_reviews,
            duplicate_reference_counts=duplicate_reference_counts,
        )

        duplicates = find_duplicate_identities(
            conn,
            company_key=keep.company_key,
            source_name_candidate=keep.source_name_candidate,
        )
        print_duplicate_report(duplicates)
        print(f"cleanup_target: keep_candidate_id={keep.id} duplicate_candidate_id={duplicate.id}")
        print(f"duplicate_reference_counts: {json.dumps(duplicate_reference_counts, sort_keys=True)}")

        if errors:
            for error in errors:
                print(f"ABORT: {error}")
            return 2

        if not args.apply:
            print("dry_run: no candidate rows were changed; pass --apply to remove the duplicate after reviewing the audit evidence")
            return 0

        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO employer_origin_candidate_cleanup_audit (
                        cleanup_type,
                        company_key,
                        source_name_candidate,
                        kept_candidate_id,
                        removed_candidate_id,
                        reviewed_by,
                        reason,
                        evidence
                    )
                    VALUES (
                        'duplicate_candidate_removed',
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s::jsonb
                    )
                    RETURNING id
                    """,
                    (
                        duplicate.company_key,
                        duplicate.source_name_candidate,
                        keep.id,
                        duplicate.id,
                        args.reviewed_by,
                        args.reason,
                        json.dumps(evidence, default=str),
                    ),
                )
                audit_id = int(cur.fetchone()["id"])
                cur.execute(
                    """
                    DELETE FROM employer_origin_source_candidates
                    WHERE id = %s
                      AND status <> 'active_controlled'
                    """,
                    (duplicate.id,),
                )
                if cur.rowcount != 1:
                    raise RuntimeError("duplicate candidate was not removed; transaction rolled back")
        print(
            "cleanup_applied: "
            f"audit_id={audit_id} kept_candidate_id={keep.id} removed_candidate_id={duplicate.id}"
        )
        return 0


def run(args: argparse.Namespace) -> int:
    targeted_args = [args.keep_candidate_id, args.duplicate_candidate_id]
    if any(value is not None for value in targeted_args) and not all(value is not None for value in targeted_args):
        raise ValueError("--keep-candidate-id and --duplicate-candidate-id must be provided together")
    if args.apply and not all(targeted_args):
        raise ValueError("--apply requires explicit --keep-candidate-id and --duplicate-candidate-id")
    if all(targeted_args):
        if not args.reviewed_by or not args.reason:
            raise ValueError("targeted cleanup requires --reviewed-by and --reason")
        return run_targeted_cleanup(args)

    with connect() as conn:
        duplicates = find_duplicate_identities(
            conn,
            company_key=args.company_key,
            source_name_candidate=args.source_name_candidate,
        )
    print_duplicate_report(duplicates)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and clean duplicate employer-origin candidate artifacts with audit evidence."
    )
    parser.add_argument("--company-key")
    parser.add_argument("--source-name-candidate")
    parser.add_argument("--keep-candidate-id", type=int)
    parser.add_argument("--duplicate-candidate-id", type=int)
    parser.add_argument("--reviewed-by")
    parser.add_argument("--reason")
    parser.add_argument("--apply", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
