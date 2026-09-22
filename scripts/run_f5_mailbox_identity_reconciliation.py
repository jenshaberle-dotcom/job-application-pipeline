#!/usr/bin/env python3
"""Deterministically reconcile duplicate mailbox-only application identities.

A duplicate is eligible only when one mailbox account + exact counterparty domain has
exactly one titled mailbox-observed application and one or more untitled mailbox-
observed applications, and none of the involved identities owns submission or
authoritative lifecycle truth. Evidence rows are re-bound; Gmail evidence itself is
never deleted or rewritten. The empty duplicate application identity is then removed.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dataclasses import dataclass  # noqa: E402
from collections import defaultdict  # noqa: E402

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig  # noqa: E402

APPROVAL_TOKEN = "F5-MAILBOX-IDENTITY-RECONCILE-V1"


@dataclass(frozen=True)
class Merge:
    canonical_id: int
    duplicate_id: int
    domain: str


def _text(value: object) -> str:
    return str(value or "").strip()


def plan(conn: object) -> list[Merge]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                a.id,
                a.discovery_kind,
                coalesce(a.job_identity_snapshot->>'job_title', '') AS job_title,
                coalesce(
                    a.job_identity_snapshot->>'counterparty_domain',
                    a.provenance->>'counterparty_domain',
                    ''
                ) AS counterparty_domain,
                coalesce(a.provenance->>'mailbox_account_fingerprint', '') AS mailbox_account,
                EXISTS (
                    SELECT 1 FROM application_submissions s
                    WHERE s.application_id = a.id
                ) AS has_submission,
                EXISTS (
                    SELECT 1 FROM application_lifecycle_events e
                    WHERE e.application_id = a.id
                ) AS has_lifecycle
            FROM applications a
            WHERE a.discovery_kind = 'mailbox_observed'
            ORDER BY a.id
            """
        )
        rows = [dict(row) for row in cur.fetchall()]

    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        domain = _text(row["counterparty_domain"]).casefold().strip(" .")
        account = _text(row["mailbox_account"])
        if not domain or not account:
            continue
        groups[(account, domain)].append(row)

    merges: list[Merge] = []
    for (_account, domain), items in groups.items():
        titled = [r for r in items if _text(r["job_title"])]
        untitled = [r for r in items if not _text(r["job_title"])]
        if len(titled) != 1 or not untitled:
            continue
        canonical = titled[0]
        involved = [canonical, *untitled]
        if any(bool(r["has_submission"]) or bool(r["has_lifecycle"]) for r in involved):
            continue
        for duplicate in untitled:
            merges.append(
                Merge(
                    canonical_id=int(canonical["id"]),
                    duplicate_id=int(duplicate["id"]),
                    domain=domain,
                )
            )
    return merges


def apply(conn: object, merges: list[Merge]) -> dict[str, int]:
    moved_candidates = 0
    deleted_applications = 0
    with conn.cursor() as cur:
        for merge in merges:
            cur.execute(
                """
                UPDATE application_event_candidates
                SET matched_application_id = %s
                WHERE matched_application_id = %s
                """,
                (merge.canonical_id, merge.duplicate_id),
            )
            moved_candidates += int(cur.rowcount)
            cur.execute(
                """
                DELETE FROM applications
                WHERE id = %s
                  AND discovery_kind = 'mailbox_observed'
                  AND NOT EXISTS (
                      SELECT 1 FROM application_submissions s
                      WHERE s.application_id = applications.id
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM application_lifecycle_events e
                      WHERE e.application_id = applications.id
                  )
                """,
                (merge.duplicate_id,),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"duplicate_delete_guard_failed:{merge.duplicate_id}")
            deleted_applications += 1
    return {
        "moved_candidates": moved_candidates,
        "deleted_applications": deleted_applications,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    args = parser.parse_args()

    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            merges = plan(conn)
            print(f"F5_MAILBOX_IDENTITY_RECONCILIATION_CANDIDATES={len(merges)}")
            for merge in merges:
                print(
                    "MERGE|canonical_id="
                    f"{merge.canonical_id}|duplicate_id={merge.duplicate_id}|domain={merge.domain}"
                )
            if not args.apply:
                conn.rollback()
                print("DATABASE_WRITES=0")
                return 0
            if args.approval_token != APPROVAL_TOKEN:
                raise RuntimeError("approval_token_invalid")
            result = apply(conn, merges)
            print(f"MOVED_CANDIDATES={result['moved_candidates']}")
            print(f"DELETED_APPLICATIONS={result['deleted_applications']}")
            print("APPLICATION_SUBMISSION_ACTIONS=0")
            print("AUTHORITATIVE_LIFECYCLE_MUTATIONS=0")
            print("EMAIL_ACTIONS=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
