"""Guarded cleanup for the audited broad-mailbox-scan false application cohort."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402
from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig  # noqa: E402

APPROVAL = "F5-MAILBOX-FALSE-POSITIVE-CLEANUP-V1"

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    args = parser.parse_args()
    with psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT a.id FROM applications a
                    WHERE a.discovery_kind='mailbox_observed'
                      AND a.created_at = TIMESTAMPTZ '2026-09-22 10:14:12.911507+00'
                      AND a.id >= 19 AND a.silver_job_id IS NULL
                      AND coalesce(a.job_identity_snapshot->>'job_title','')=''
                      AND coalesce(a.job_identity_snapshot->>'employer_name','')=''
                      AND NOT EXISTS (
                        SELECT 1 FROM application_submissions s WHERE s.application_id=a.id
                      )
                    ORDER BY a.id
                """)
                ids = [int(row["id"]) for row in cur.fetchall()]
                print("CANDIDATES=" + ",".join(map(str, ids)))
                print("CANDIDATE_COUNT=" + str(len(ids)))
                if not args.apply:
                    print("DATABASE_WRITES=0")
                    return 0
                if args.approval_token != APPROVAL:
                    raise SystemExit("approval token required")
                if len(ids) != 19:
                    raise SystemExit(f"guard expected 19 audited candidates, got {len(ids)}")
                cur.execute("""
                    UPDATE application_event_candidates
                    SET matched_application_id=NULL, match_status='unmatched',
                        ambiguity_reason='no_safe_application_identity',
                        review_status='ambiguous'
                    WHERE matched_application_id = ANY(%s) AND is_active
                """, (ids,))
                moved = cur.rowcount
                cur.execute("DELETE FROM applications WHERE id = ANY(%s)", (ids,))
                print("EVIDENCE_MOVED_TO_REVIEW=" + str(moved))
                print("APPLICATIONS_DELETED=" + str(cur.rowcount))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
