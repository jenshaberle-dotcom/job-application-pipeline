"""Run the integrated Product V1 Pipeline cycle.

Default mode is read-only planning. External StepStone access and DB review-state
writes require separate explicit flags. No provider or application submission is
implemented here.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from typing import Any

from psycopg.rows import dict_row

from scripts.run_stepstone_company_discovery_cycle_agent import (
    DEFAULT_SOURCE_NAME,
    apply_cooldowns_from_review,
    assess_discovery_observations,
    connect,
    fetch_stepstone_observations,
    load_active_company_cooldowns,
    write_review,
)
from src.search_intelligence.stepstone_company_discovery_cycle import (
    DEFAULT_MAX_NOT_TERMS_PER_REQUEST,
    DEFAULT_NOT_ENABLED_SEARCH_TERMS,
    build_company_discovery_plan,
)
from src.search_intelligence.stepstone_wave_rotation import (
    next_wave_transition,
    resolve_wave_index,
)


def load_due_wave_terms(
    conn: Any,
    *,
    search_profile_name: str,
    limit: int,
    force_terms: tuple[str, ...],
) -> list[dict[str, Any]]:
    where = "AND lower(search_term) = ANY(%s::text[])" if force_terms else "AND (next_due_at IS NULL OR next_due_at <= now())"
    params: list[object] = [DEFAULT_SOURCE_NAME, search_profile_name]
    if force_terms:
        params.append([term.lower() for term in force_terms])
    params.append(limit)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT
                source_name,
                search_profile_name,
                search_term,
                current_interval_days,
                min_interval_days,
                max_interval_days,
                is_not_exclusion_enabled,
                current_exclusion_wave_index
            FROM search_term_cycle_state
            WHERE source_name = %s
              AND search_profile_name = %s
              {where}
            ORDER BY next_due_at NULLS FIRST, search_term
            LIMIT %s
            """,
            params,
        )
        return [dict(row) for row in cur.fetchall()]


def persist_cycle_outcome(
    conn: Any,
    *,
    row: dict[str, Any],
    plan: Any,
    assessment: Any,
) -> int:
    current_index = int(row.get("current_exclusion_wave_index", 0) or 0)
    transition = next_wave_transition(
        current_index=current_index,
        action=plan.action,
        boundary=plan.boundary,
    )
    interval = int(assessment.recommended_interval_days)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE search_term_cycle_state
            SET
                current_interval_days = %s,
                last_run_at = now(),
                next_due_at = now() + (%s || ' days')::interval,
                last_quality_score = %s,
                last_new_company_count = %s,
                last_known_cooldown_hit_count = %s,
                current_exclusion_wave_index = %s,
                last_wave_action = %s,
                last_wave_completed_at = now(),
                updated_at = now()
            WHERE source_name = %s
              AND search_profile_name = %s
              AND search_term = %s
            """,
            (
                interval,
                interval,
                assessment.quality_score,
                assessment.new_company_count,
                assessment.known_cooldown_hit_count,
                transition.next_index,
                plan.action,
                row["source_name"],
                row["search_profile_name"],
                row["search_term"],
            ),
        )
    conn.commit()
    return transition.next_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-profile-name", default="stepstone_data_engineer_hannover")
    parser.add_argument("--limit-search-terms", type=int, default=2)
    parser.add_argument("--force-search-term", action="append", default=[])
    parser.add_argument("--wave-index", type=int, default=None, help="Diagnostic override; persisted wave state is used by default.")
    parser.add_argument("--max-not-terms-per-request", type=int, default=DEFAULT_MAX_NOT_TERMS_PER_REQUEST)
    parser.add_argument("--fetch-stepstone", action="store_true", help="Explicitly allow one bounded result page per selected term.")
    parser.add_argument("--write-review-state", action="store_true")
    parser.add_argument("--apply-cooldowns", action="store_true")
    parser.add_argument("--reviewed-by", default="jens")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.apply_cooldowns and not args.write_review_state:
        raise SystemExit("--apply-cooldowns requires --write-review-state")
    if args.write_review_state and not args.fetch_stepstone:
        raise SystemExit("--write-review-state requires --fetch-stepstone so persisted review state reflects an actual bounded observation")

    results: list[dict[str, object]] = []
    with connect() as conn:
        rows = load_due_wave_terms(
            conn,
            search_profile_name=args.search_profile_name,
            limit=args.limit_search_terms,
            force_terms=tuple(args.force_search_term),
        )
        cooldowns = load_active_company_cooldowns(
            conn,
            source_name=DEFAULT_SOURCE_NAME,
            search_profile_name=args.search_profile_name,
        )

        for row in rows:
            persisted_index = int(row.get("current_exclusion_wave_index", 0) or 0)
            wave_index = resolve_wave_index(
                persisted_index=persisted_index,
                override_index=args.wave_index,
            )
            search_term = str(row["search_term"])
            plan = build_company_discovery_plan(
                source_name=DEFAULT_SOURCE_NAME,
                search_profile_name=args.search_profile_name,
                search_term=search_term,
                cooldowns=cooldowns,
                enabled_terms=DEFAULT_NOT_ENABLED_SEARCH_TERMS,
                max_not_terms_per_request=args.max_not_terms_per_request,
                exclusion_wave_index=wave_index,
            )

            observations = []
            assessment = None
            final_url = None
            review_id = None
            next_wave_index = persisted_index

            if args.fetch_stepstone and plan.action != "skip_empty_exclusion_wave":
                observations, final_url = fetch_stepstone_observations(plan)
                assessment = assess_discovery_observations(
                    search_term=search_term,
                    observations=observations,
                    cooldown_company_keys=plan.not_company_keys,
                    current_interval_days=int(row["current_interval_days"]),
                    min_interval_days=int(row["min_interval_days"]),
                    max_interval_days=int(row["max_interval_days"]),
                )

            if args.write_review_state and assessment is not None:
                review_id = write_review(
                    conn,
                    plan=plan,
                    assessment=assessment,
                    observations=observations,
                    reviewed_by=args.reviewed_by,
                )
                next_wave_index = persist_cycle_outcome(
                    conn,
                    row=row,
                    plan=plan,
                    assessment=assessment,
                )
                if args.apply_cooldowns:
                    apply_cooldowns_from_review(conn, review_id=review_id)

            results.append(
                {
                    "search_term": search_term,
                    "action": plan.action,
                    "planned_query": plan.planned_query,
                    "persisted_wave_index": persisted_index,
                    "effective_wave_index": wave_index,
                    "next_wave_index": next_wave_index,
                    "selected_company_exclusions": list(plan.not_company_names),
                    "cooldown_pool_size": plan.boundary.get("cooldown_pool_size", 0),
                    "fetch_performed": bool(args.fetch_stepstone and plan.action != "skip_empty_exclusion_wave"),
                    "final_url": final_url,
                    "observed_count": len(observations),
                    "review_id": review_id,
                }
            )

    output = {
        "schema_version": "pipeline.product_v1.monolith_run.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "mode": {
            "stepstone_fetch": args.fetch_stepstone,
            "write_review_state": args.write_review_state,
            "apply_cooldowns": args.apply_cooldowns,
            "provider_calls": False,
            "application_submission": False,
        },
        "wave_results": results,
        "next_surfaces": {
            "top5": "served only after approved ranking policy and DB-backed assessments",
            "application_assistant": "blocked until approved base CV and base application letter are registered",
            "react_control_center": "read-only API and frontend source available",
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
