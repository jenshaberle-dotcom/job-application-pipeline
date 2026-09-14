"""Run the F4A-R2 read-only requirement plan against operator-visible current truth.

F4A-R2 exists to repair the evidence shown in the Control Center. Therefore its
cohort must be the same normal review scope the operator actually sees, not the
larger lifecycle-current storage projection. The Control Center already applies
bounded presentation-only geography filtering and exact Origin identity dedup to
that scope; neither operation grants ranking or application authority.

This diagnostic deliberately does *not* treat source activation/admission as a
second gate for reading public job-side requirement evidence. A row first has to
be in the canonical Product current projection and then survive the exact same
operator presentation projection used by ``/api/v1/product-v1``. The diagnostic
still fetches only the exact persisted HTTPS detail URL, rejects cross-origin
redirects, never reads Candidate Facts, never writes the database, and grants no
ranking, Top-5, capability-fit or application authority.

The shim is intentionally diagnostic-only. A later persistence/apply path must
bind job-side evidence to this same operator-review cohort without using the
read-only projection to create source activation or Product authority.
"""

from __future__ import annotations

from typing import Any, Mapping

import psycopg

from scripts import run_f4a_r2_current_requirement_plan as plan
from scripts.product_v1_job_presentation_runtime import (
    enrich_product_payload_for_operator,
)
from scripts.run_product_v1_control_center import load_product_v1_payload


CURRENT_PRODUCT_AUTHORITY = "operator_review_scope_current_origin"
_CANONICAL_LOAD_CURRENT_ROWS = plan._load_current_rows


def _review_scope_ids(payload: Mapping[str, object]) -> set[int]:
    result: set[int] = set()
    rows = payload.get("job_readiness")
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        value = row.get("silver_job_id")
        try:
            silver_job_id = int(value) if value is not None else 0
        except (TypeError, ValueError):
            continue
        if silver_job_id > 0:
            result.add(silver_job_id)
    return result


def _operator_review_rows(conn: psycopg.Connection[Any]) -> list[dict[str, object]]:
    """Return assessment rows for exactly the normal Control Center review scope."""

    operator_payload = enrich_product_payload_for_operator(load_product_v1_payload())
    review_ids = _review_scope_ids(operator_payload)
    if not review_ids:
        return []
    return [
        row
        for row in _CANONICAL_LOAD_CURRENT_ROWS(conn)
        if int(row.get("current_silver_job_id") or 0) in review_ids
    ]


def _current_product_sources(conn: psycopg.Connection[Any]) -> dict[str, str]:
    """Return sources represented by the operator-visible current review scope."""

    rows = _operator_review_rows(conn)
    return {
        source_name: CURRENT_PRODUCT_AUTHORITY
        for row in rows
        if (source_name := str(row.get("source_name") or "").strip())
    }


def main() -> int:
    plan._load_current_rows = _operator_review_rows
    plan._load_authorized_sources = _current_product_sources
    return plan.main()


if __name__ == "__main__":
    raise SystemExit(main())
