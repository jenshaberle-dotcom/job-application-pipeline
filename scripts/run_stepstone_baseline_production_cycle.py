"""Run one fail-closed StepStone baseline production cycle.

The active baseline-only mode performs at most one unfiltered StepStone page-one
request. It persists review evidence, deduplicated discovery candidates, compact
company-title vocabulary, a non-active suppression-set candidate, and bounded
origin refresh/discovery signals.

Multi-company NOT filtering remains blocked until a validated query transport
and approved filter capacity exist. No pagination, detail pages, provider calls,
connector execution, source activation, Bronze/Silver writes, scheduler changes,
or application actions occur.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.activate_stepstone_baseline_runtime import (
    connect,
    ensure_runtime_schema,
    load_unpersisted_review_observations,
    persist_review_observations,
)
from scripts.run_stepstone_company_discovery_cycle_agent import (
    fetch_stepstone_observations,
    write_review,
)
from src.normalization.company_keys import (
    find_matching_company_key,
    normalize_company_key,
)
from src.search_intelligence.stepstone_company_discovery_cycle import (
    CompanyObservation,
    StepStoneCompanyDiscoveryPlan,
    assess_discovery_observations,
)
from src.search_intelligence.stepstone_decoupled_cycle_policy import (
    BaselineCompanyObservation,
    DecoupledCyclePolicy,
    OriginConnectorState,
    build_suppression_set_from_baseline,
    plan_origin_refresh_decisions,
)

APPROVAL_TOKEN = "run_stepstone_baseline_production_cycle"


def load_activation(
    conn: psycopg.Connection[Any],
    *,
    source_name: str,
    search_profile_name: str,
    search_term: str,
    location: str,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM stepstone_runtime_activations
            WHERE source_name = %s
              AND search_profile_name = %s
              AND search_term = %s
              AND search_location = %s
            """,
            (source_name, search_profile_name, search_term, location),
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("No StepStone runtime activation exists for this scope")
    activation = dict(row)
    if activation["status"] != "baseline_only_active":
        raise RuntimeError(
            "This runner requires status=baseline_only_active; "
            f"current status={activation['status']}"
        )
    return activation


def load_baseline_cycle_state(
    conn: psycopg.Connection[Any],
    *,
    source_name: str,
    search_profile_name: str,
    search_term: str,
) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM stepstone_baseline_cycle_state
            WHERE source_name = %s
              AND search_profile_name = %s
              AND search_term = %s
            """,
            (source_name, search_profile_name, search_term),
        )
        row = cur.fetchone()
    return dict(row) if row is not None else None


def baseline_is_due(
    state: dict[str, Any] | None,
    *,
    now: datetime,
    force: bool,
) -> tuple[bool, str]:
    if force:
        return True, "operator_forced_baseline"
    if state is None or state.get("last_baseline_at") is None:
        return True, "no_valid_baseline_exists"
    if bool(state.get("transport_health_degraded")):
        return True, "transport_health_requires_recalibration"
    if bool(state.get("vocabulary_refresh_due")):
        return True, "company_vocabulary_refresh_due"
    if bool(state.get("novelty_degraded")):
        return True, "filtered_discovery_novelty_degraded"
    due_at = state.get("next_baseline_due_at")
    if due_at is None or now >= due_at:
        return True, "baseline_refresh_interval_elapsed"
    return False, "baseline_not_due"


def build_baseline_plan(
    *,
    source_name: str,
    search_profile_name: str,
    search_term: str,
    run_reason: str,
) -> StepStoneCompanyDiscoveryPlan:
    return StepStoneCompanyDiscoveryPlan(
        source_name=source_name,
        search_profile_name=search_profile_name,
        search_term=search_term,
        base_query=search_term,
        planned_query=search_term,
        not_company_names=(),
        not_company_keys=(),
        action="run_production_baseline_census",
        reason=run_reason,
        boundary={
            "page_one_only": True,
            "maximum_requests": 1,
            "unfiltered_baseline": True,
            "candidate_persistence": "discovery_status_only",
            "multi_not_filtering": "blocked_pending_transport_and_capacity_validation",
            "no_pagination": True,
            "no_detail_pages": True,
            "no_connector_execution": True,
            "no_source_activation": True,
            "no_bronze_or_silver_write": True,
            "no_provider_call": True,
            "no_scheduler_mutation": True,
            "no_application_action": True,
        },
    )


def aggregate_baseline_observations(
    observations: list[CompanyObservation],
) -> list[BaselineCompanyObservation]:
    return [
        BaselineCompanyObservation(
            company_key=observation.company_key,
            company_name=observation.company_name,
            card_count=1,
            first_position=index,
        )
        for index, observation in enumerate(observations, start=1)
    ]


def persist_suppression_candidate(
    conn: psycopg.Connection[Any],
    *,
    source_name: str,
    search_profile_name: str,
    search_term: str,
    review_id: int,
    observations: list[CompanyObservation],
    policy: DecoupledCyclePolicy,
    observed_at: datetime,
) -> int:
    selection = build_suppression_set_from_baseline(
        observations=aggregate_baseline_observations(observations),
        policy=policy,
        baseline_review_id=review_id,
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE stepstone_filter_suppression_sets
            SET status = 'superseded',
                superseded_at = now()
            WHERE source_name = %s
              AND search_profile_name = %s
              AND search_term = %s
              AND status IN ('diagnostic_only', 'candidate')
            """,
            (source_name, search_profile_name, search_term),
        )
        cur.execute(
            """
            INSERT INTO stepstone_filter_suppression_sets (
                source_name,
                search_profile_name,
                search_term,
                baseline_review_id,
                baseline_observed_at,
                baseline_observed_count,
                baseline_distinct_company_count,
                requested_filter_count,
                selected_filter_count,
                transport_name,
                transport_status,
                status,
                policy_version
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                NULL, 'unvalidated', 'candidate', %s
            )
            RETURNING id
            """,
            (
                source_name,
                search_profile_name,
                search_term,
                review_id,
                observed_at,
                selection.baseline_observed_count,
                selection.baseline_distinct_company_count,
                selection.requested_filter_count,
                selection.selected_filter_count,
                selection.policy_version,
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("suppression candidate insert returned no id")
        suppression_set_id = int(row["id"])
        for item in selection.items:
            cur.execute(
                """
                INSERT INTO stepstone_filter_suppression_set_items (
                    suppression_set_id,
                    company_key,
                    company_name,
                    filter_alias,
                    baseline_card_count,
                    baseline_card_share,
                    first_position,
                    selection_rank
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    suppression_set_id,
                    item.company_key,
                    item.company_name,
                    item.filter_alias,
                    item.baseline_card_count,
                    item.baseline_card_share,
                    item.first_position,
                    item.selection_rank,
                ),
            )
    return suppression_set_id


def update_baseline_state(
    conn: psycopg.Connection[Any],
    *,
    source_name: str,
    search_profile_name: str,
    search_term: str,
    review_id: int | None,
    observed_at: datetime,
    refresh_hours: int,
    policy_version: str,
    transport_health_degraded: bool,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO stepstone_baseline_cycle_state (
                source_name,
                search_profile_name,
                search_term,
                last_baseline_review_id,
                active_suppression_set_id,
                last_baseline_at,
                next_baseline_due_at,
                filtered_runs_since_baseline,
                vocabulary_refresh_due,
                vocabulary_refresh_reason,
                novelty_degraded,
                transport_health_degraded,
                last_run_mode,
                last_run_at,
                policy_version
            ) VALUES (
                %s, %s, %s, %s, NULL,
                %s, %s, 0, false, NULL, false, %s,
                'baseline', %s, %s
            )
            ON CONFLICT (source_name, search_profile_name, search_term)
            DO UPDATE SET
                last_baseline_review_id = EXCLUDED.last_baseline_review_id,
                active_suppression_set_id = NULL,
                last_baseline_at = EXCLUDED.last_baseline_at,
                next_baseline_due_at = EXCLUDED.next_baseline_due_at,
                filtered_runs_since_baseline = 0,
                vocabulary_refresh_due = false,
                vocabulary_refresh_reason = NULL,
                novelty_degraded = false,
                transport_health_degraded = EXCLUDED.transport_health_degraded,
                last_run_mode = 'baseline',
                last_run_at = EXCLUDED.last_run_at,
                policy_version = EXCLUDED.policy_version,
                updated_at = now()
            """,
            (
                source_name,
                search_profile_name,
                search_term,
                review_id,
                observed_at,
                observed_at + timedelta(hours=refresh_hours),
                transport_health_degraded,
                observed_at,
                policy_version,
            ),
        )


def load_origin_connector_states(
    conn: psycopg.Connection[Any],
    *,
    observations: list[CompanyObservation],
) -> list[OriginConnectorState]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                company_key,
                company_name,
                status,
                source_name_candidate
            FROM employer_origin_source_candidates
            ORDER BY id
            """
        )
        candidates = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            SELECT
                company_key,
                refresh_pending,
                refresh_cooldown_until
            FROM stepstone_origin_refresh_state
            """
        )
        refresh_by_key = {
            normalize_company_key(row["company_key"]): dict(row)
            for row in cur.fetchall()
        }

    candidate_by_key = {
        normalize_company_key(row["company_key"] or row["company_name"]): row
        for row in candidates
        if normalize_company_key(row["company_key"] or row["company_name"])
    }
    states: list[OriginConnectorState] = []
    seen: set[str] = set()
    for observation in observations:
        key = normalize_company_key(
            observation.company_key or observation.company_name
        )
        if not key or key in seen:
            continue
        seen.add(key)
        matched_key = find_matching_company_key(key, set(candidate_by_key))
        candidate = candidate_by_key.get(matched_key) if matched_key else None
        refresh = refresh_by_key.get(key, {})
        states.append(
            OriginConnectorState(
                company_key=key,
                has_origin_connector=bool(
                    candidate and candidate.get("status") == "active_controlled"
                ),
                refresh_pending=bool(refresh.get("refresh_pending", False)),
                refresh_cooldown_until=refresh.get("refresh_cooldown_until"),
            )
        )
    return states


def persist_origin_signals(
    conn: psycopg.Connection[Any],
    *,
    source_name: str,
    search_profile_name: str,
    search_term: str,
    review_id: int,
    observations: list[CompanyObservation],
    policy: DecoupledCyclePolicy,
    observed_at: datetime,
) -> dict[str, int]:
    baseline_observations = aggregate_baseline_observations(observations)
    connector_states = load_origin_connector_states(
        conn,
        observations=observations,
    )
    decisions = plan_origin_refresh_decisions(
        baseline_observations=baseline_observations,
        connector_states=connector_states,
        policy=policy,
        now=observed_at,
    )
    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        for decision in decisions:
            counts[decision.action] = counts.get(decision.action, 0) + 1
            refresh_pending = decision.action == "trigger_origin_refresh"
            cooldown_until = (
                observed_at + timedelta(hours=policy.origin_refresh_cooldown_hours)
                if refresh_pending
                else None
            )
            cur.execute(
                """
                INSERT INTO stepstone_origin_refresh_state (
                    source_name,
                    search_profile_name,
                    search_term,
                    company_key,
                    company_name,
                    has_origin_connector,
                    origin_connector_key,
                    refresh_pending,
                    refresh_cooldown_until,
                    last_triggered_at,
                    last_baseline_observed_at,
                    last_baseline_card_count,
                    last_baseline_card_share,
                    total_trigger_count,
                    total_deduplicated_count
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, NULL, %s, %s,
                    CASE WHEN %s THEN %s ELSE NULL END,
                    %s, %s, %s,
                    CASE WHEN %s THEN 1 ELSE 0 END,
                    CASE WHEN %s THEN 1 ELSE 0 END
                )
                ON CONFLICT (
                    source_name,
                    search_profile_name,
                    search_term,
                    company_key
                ) DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    has_origin_connector = EXCLUDED.has_origin_connector,
                    refresh_pending = CASE
                        WHEN EXCLUDED.refresh_pending THEN true
                        ELSE stepstone_origin_refresh_state.refresh_pending
                    END,
                    refresh_cooldown_until = COALESCE(
                        EXCLUDED.refresh_cooldown_until,
                        stepstone_origin_refresh_state.refresh_cooldown_until
                    ),
                    last_triggered_at = COALESCE(
                        EXCLUDED.last_triggered_at,
                        stepstone_origin_refresh_state.last_triggered_at
                    ),
                    last_baseline_observed_at = EXCLUDED.last_baseline_observed_at,
                    last_baseline_card_count = EXCLUDED.last_baseline_card_count,
                    last_baseline_card_share = EXCLUDED.last_baseline_card_share,
                    total_trigger_count =
                        stepstone_origin_refresh_state.total_trigger_count
                        + EXCLUDED.total_trigger_count,
                    total_deduplicated_count =
                        stepstone_origin_refresh_state.total_deduplicated_count
                        + EXCLUDED.total_deduplicated_count,
                    updated_at = now()
                """,
                (
                    source_name,
                    search_profile_name,
                    search_term,
                    decision.company_key,
                    decision.company_name,
                    decision.action != "origin_discovery_signal",
                    refresh_pending,
                    cooldown_until,
                    refresh_pending,
                    observed_at,
                    observed_at,
                    decision.card_count,
                    decision.card_share,
                    refresh_pending,
                    decision.action.startswith("deduplicated_"),
                ),
            )
            cur.execute(
                """
                INSERT INTO stepstone_origin_refresh_signals (
                    source_name,
                    search_profile_name,
                    search_term,
                    baseline_review_id,
                    company_key,
                    company_name,
                    card_count,
                    card_share,
                    action,
                    reason,
                    origin_connector_key
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, NULL
                )
                """,
                (
                    source_name,
                    search_profile_name,
                    search_term,
                    review_id,
                    decision.company_key,
                    decision.company_name,
                    decision.card_count,
                    decision.card_share,
                    decision.action,
                    decision.reason,
                ),
            )
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-name", default="stepstone")
    parser.add_argument(
        "--search-profile-name",
        default="stepstone_data_engineer_hannover",
    )
    parser.add_argument("--search-term", default="Machine Learning Engineer")
    parser.add_argument("--location", default="Hannover")
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--approval-token", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.approval_token != APPROVAL_TOKEN:
        raise SystemExit("ABORT: exact --approval-token is required")

    observed_at = datetime.now(UTC)
    with connect() as conn:
        ensure_runtime_schema(conn)
        activation = load_activation(
            conn,
            source_name=args.source_name,
            search_profile_name=args.search_profile_name,
            search_term=args.search_term,
            location=args.location,
        )
        state = load_baseline_cycle_state(
            conn,
            source_name=args.source_name,
            search_profile_name=args.search_profile_name,
            search_term=args.search_term,
        )
        due, run_reason = baseline_is_due(
            state,
            now=observed_at,
            force=args.force,
        )
        if not due:
            print("StepStone baseline production cycle")
            print("action: skip_not_due")
            print(f"reason: {run_reason}")
            print("requests: 0/1")
            print("RESULT: STEPSTONE_BASELINE_PRODUCTION_CYCLE_SKIPPED")
            return

        policy = DecoupledCyclePolicy(
            requested_filter_count=int(activation["requested_filter_count"]),
            baseline_refresh_interval_hours=int(
                activation["baseline_refresh_interval_hours"]
            ),
            max_filtered_runs_between_baselines=int(
                activation["max_filtered_runs_between_baselines"]
            ),
            vocabulary_staleness_hours=int(
                activation["vocabulary_staleness_hours"]
            ),
            origin_refresh_cooldown_hours=int(
                activation["origin_refresh_cooldown_hours"]
            ),
            dominance_min_cards=int(activation["dominance_min_cards"]),
            dominance_min_share=float(activation["dominance_min_share"]),
            policy_version=str(activation["policy_version"]),
        )
        plan = build_baseline_plan(
            source_name=args.source_name,
            search_profile_name=args.search_profile_name,
            search_term=args.search_term,
            run_reason=run_reason,
        )

        observations, final_url = fetch_stepstone_observations(plan)
        assessment = assess_discovery_observations(
            search_term=args.search_term,
            observations=observations,
            cooldown_company_keys=(),
            current_interval_days=1,
            min_interval_days=1,
            max_interval_days=14,
        )
        review_id = write_review(
            conn,
            plan=plan,
            assessment=assessment,
            observations=observations,
            reviewed_by=args.reviewed_by,
        )

        if not observations:
            update_baseline_state(
                conn,
                source_name=args.source_name,
                search_profile_name=args.search_profile_name,
                search_term=args.search_term,
                review_id=review_id,
                observed_at=observed_at,
                refresh_hours=policy.baseline_refresh_interval_hours,
                policy_version=policy.policy_version,
                transport_health_degraded=True,
            )
            conn.commit()
            raise SystemExit(
                "ABORT: baseline returned zero parseable cards; review persisted, "
                "transport marked degraded, no candidates created"
            )

        review_observations = load_unpersisted_review_observations(
            conn,
            review_ids=(review_id,),
        )
        _, created, matched, vocabulary = persist_review_observations(
            conn,
            observations=review_observations,
            persisted_by=args.reviewed_by,
            apply=True,
            event_source_mode="baseline",
        )
        suppression_set_id = persist_suppression_candidate(
            conn,
            source_name=args.source_name,
            search_profile_name=args.search_profile_name,
            search_term=args.search_term,
            review_id=review_id,
            observations=observations,
            policy=policy,
            observed_at=observed_at,
        )
        origin_counts = persist_origin_signals(
            conn,
            source_name=args.source_name,
            search_profile_name=args.search_profile_name,
            search_term=args.search_term,
            review_id=review_id,
            observations=observations,
            policy=policy,
            observed_at=observed_at,
        )
        update_baseline_state(
            conn,
            source_name=args.source_name,
            search_profile_name=args.search_profile_name,
            search_term=args.search_term,
            review_id=review_id,
            observed_at=observed_at,
            refresh_hours=policy.baseline_refresh_interval_hours,
            policy_version=policy.policy_version,
            transport_health_degraded=False,
        )
        conn.commit()

    print("StepStone baseline production cycle")
    print("runtime_status: baseline_only_active")
    print("requests: 1/1")
    print(f"final_url: {final_url}")
    print(f"review_id: {review_id}")
    print(f"observed_cards: {len(observations)}/25")
    print(f"distinct_companies: {assessment.distinct_company_count}")
    print(f"created_discovery_candidates: {created}")
    print(f"matched_existing_candidates: {matched}")
    print(f"title_vocabulary_upserts: {vocabulary}")
    print(f"suppression_candidate_set_id: {suppression_set_id}")
    print(f"origin_signal_counts: {origin_counts}")
    print("multi_not_production_status: blocked_pending_transport_and_capacity_validation")
    print("RESULT: STEPSTONE_BASELINE_PRODUCTION_CYCLE_COMPLETED")


if __name__ == "__main__":
    main()
