"""Reconcile StepStone search-term cycle state to active search-profile truth.

Default mode is read-only planning. ``--apply`` requires the exact approval token
and mutates only ``search_term_cycle_state`` for the requested StepStone profile.
No StepStone request, provider/model/Tavily call, candidate/source/connector
mutation, scheduler change, Bronze/Silver/Product/ranking/application write is
performed by this command.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from src.config import get_database_config  # noqa: E402
from src.search_intelligence.search_term_cycle_state_reconcile import (  # noqa: E402
    CycleStateReconcilePlan,
    normalize_search_term,
    plan_cycle_state_reconcile,
)
from src.search_intelligence.stepstone_company_discovery_cycle import (  # noqa: E402
    DEFAULT_NOT_ENABLED_SEARCH_TERMS,
)

DEFAULT_SOURCE_NAME = "stepstone"
DEFAULT_PROFILE_NAME = "stepstone_data_engineer_hannover"
APPROVAL_TOKEN = "RECONCILE-STEPSTONE-CYCLE-STATE-001"


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def load_active_terms(
    conn: psycopg.Connection[Any], *, source_name: str, search_profile_name: str
) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT st.search_term
            FROM search_profiles sp
            JOIN search_terms st ON st.search_profile_id = sp.id
            WHERE sp.source_name = %s
              AND sp.profile_name = %s
              AND sp.is_active = true
              AND st.is_active = true
            ORDER BY st.id
            """,
            (source_name, search_profile_name),
        )
        return [str(row["search_term"]) for row in cur.fetchall()]


def load_cycle_terms(
    conn: psycopg.Connection[Any], *, source_name: str, search_profile_name: str
) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT search_term
            FROM search_term_cycle_state
            WHERE source_name = %s
              AND search_profile_name = %s
            ORDER BY id
            """,
            (source_name, search_profile_name),
        )
        return [str(row["search_term"]) for row in cur.fetchall()]


def _enabled_not_keys() -> set[str]:
    return {normalize_search_term(term) for term in DEFAULT_NOT_ENABLED_SEARCH_TERMS}


def apply_plan(
    conn: psycopg.Connection[Any],
    *,
    source_name: str,
    search_profile_name: str,
    plan: CycleStateReconcilePlan,
) -> None:
    enabled_not_keys = _enabled_not_keys()
    with conn.cursor() as cur:
        for stale_term in plan.removed_terms:
            cur.execute(
                """
                DELETE FROM search_term_cycle_state
                WHERE source_name = %s
                  AND search_profile_name = %s
                  AND search_term = %s
                """,
                (source_name, search_profile_name, stale_term),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"expected exactly one stale cycle-state row for {stale_term!r}")

        for previous_term, canonical_term in plan.canonicalized_terms:
            cur.execute(
                """
                UPDATE search_term_cycle_state
                SET search_term = %s,
                    is_not_exclusion_enabled = %s,
                    updated_at = now()
                WHERE source_name = %s
                  AND search_profile_name = %s
                  AND search_term = %s
                """,
                (
                    canonical_term,
                    normalize_search_term(canonical_term) in enabled_not_keys,
                    source_name,
                    search_profile_name,
                    previous_term,
                ),
            )
            if cur.rowcount != 1:
                raise RuntimeError(
                    f"expected exactly one retained cycle-state row for {previous_term!r}"
                )

        canonicalized_targets = {new for _, new in plan.canonicalized_terms}
        for retained_term in plan.retained_terms:
            if retained_term in canonicalized_targets:
                continue
            cur.execute(
                """
                UPDATE search_term_cycle_state
                SET is_not_exclusion_enabled = %s,
                    updated_at = CASE
                        WHEN is_not_exclusion_enabled IS DISTINCT FROM %s THEN now()
                        ELSE updated_at
                    END
                WHERE source_name = %s
                  AND search_profile_name = %s
                  AND search_term = %s
                """,
                (
                    normalize_search_term(retained_term) in enabled_not_keys,
                    normalize_search_term(retained_term) in enabled_not_keys,
                    source_name,
                    search_profile_name,
                    retained_term,
                ),
            )
            if cur.rowcount != 1:
                raise RuntimeError(
                    f"expected exactly one retained cycle-state row for {retained_term!r}"
                )

        for new_term in plan.added_terms:
            cur.execute(
                """
                INSERT INTO search_term_cycle_state (
                    source_name,
                    search_profile_name,
                    search_term,
                    is_not_exclusion_enabled,
                    next_due_at
                ) VALUES (%s, %s, %s, %s, now())
                """,
                (
                    source_name,
                    search_profile_name,
                    new_term,
                    normalize_search_term(new_term) in enabled_not_keys,
                ),
            )

    final_terms = load_cycle_terms(
        conn, source_name=source_name, search_profile_name=search_profile_name
    )
    final_plan = plan_cycle_state_reconcile(
        active_terms=list(plan.active_terms), current_terms=final_terms
    )
    if final_plan.changed:
        raise RuntimeError(
            "cycle-state reconciliation did not converge: "
            + json.dumps(_plan_payload(final_plan), sort_keys=True)
        )
    conn.commit()


def _plan_payload(plan: CycleStateReconcilePlan) -> dict[str, object]:
    return {
        "active_terms": list(plan.active_terms),
        "current_terms": list(plan.current_terms),
        "retained_terms": list(plan.retained_terms),
        "added_terms": list(plan.added_terms),
        "removed_terms": list(plan.removed_terms),
        "canonicalized_terms": [list(item) for item in plan.canonicalized_terms],
        "changed": plan.changed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-name", default=DEFAULT_SOURCE_NAME)
    parser.add_argument("--search-profile-name", default=DEFAULT_PROFILE_NAME)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.source_name != DEFAULT_SOURCE_NAME:
        raise SystemExit("this bounded command is StepStone-only")
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit("--apply requires the exact cycle-state reconciliation approval token")

    with connect() as conn:
        active_terms = load_active_terms(
            conn,
            source_name=args.source_name,
            search_profile_name=args.search_profile_name,
        )
        current_terms = load_cycle_terms(
            conn,
            source_name=args.source_name,
            search_profile_name=args.search_profile_name,
        )
        plan = plan_cycle_state_reconcile(
            active_terms=active_terms,
            current_terms=current_terms,
        )
        before = _plan_payload(plan)
        if args.apply:
            apply_plan(
                conn,
                source_name=args.source_name,
                search_profile_name=args.search_profile_name,
                plan=plan,
            )
        after_terms = load_cycle_terms(
            conn,
            source_name=args.source_name,
            search_profile_name=args.search_profile_name,
        )
        after = plan_cycle_state_reconcile(
            active_terms=active_terms,
            current_terms=after_terms,
        )

    print(
        json.dumps(
            {
                "source_name": args.source_name,
                "search_profile_name": args.search_profile_name,
                "mode": "apply" if args.apply else "plan",
                "approval_token_required": APPROVAL_TOKEN,
                "before": before,
                "after": _plan_payload(after),
                "provider_requests": 0,
                "tavily_requests": 0,
                "connector_mutation": False,
                "scheduler_mutation": False,
                "product_mutation": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
