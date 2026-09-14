"""Run the F4A-R2 read-only requirement plan against canonical current-job truth.

This diagnostic deliberately does *not* treat source activation/admission as a
second gate for reading public job-side requirement evidence. Membership in
``gold_current_job_opportunities`` is already the canonical current-vacancy
projection used by the Product surface. The diagnostic still fetches only the
exact persisted HTTPS detail URL, rejects cross-origin redirects, never reads
Candidate Facts, never writes the database, and grants no ranking, Top-5,
capability-fit or application authority.

The shim is intentionally diagnostic-only. A later persistence/apply path must
bind job-side evidence without using this read-only projection to create source
activation or Product authority.
"""

from __future__ import annotations

from typing import Any

import psycopg

from scripts import run_f4a_r2_current_requirement_plan as plan


CURRENT_PRODUCT_AUTHORITY = "gold_current_job_opportunity_membership"


def _current_product_sources(conn: psycopg.Connection[Any]) -> dict[str, str]:
    """Return sources represented by the canonical current Product projection."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT source_name
            FROM gold_current_job_opportunities
            WHERE source_name IS NOT NULL
              AND btrim(source_name) <> ''
            ORDER BY source_name
            """
        )
        return {
            str(row["source_name"]): CURRENT_PRODUCT_AUTHORITY
            for row in cur.fetchall()
        }


def main() -> int:
    plan._load_authorized_sources = _current_product_sources
    return plan.main()


if __name__ == "__main__":
    raise SystemExit(main())
