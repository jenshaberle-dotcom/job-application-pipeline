"""Activate fail-closed StepStone baseline runtime and backfill candidates.

The activation enables one unfiltered page-one census per future production run.
Multi-company NOT filtering remains blocked until query transport and filter
capacity are validated. Existing StepStone ``observed_company`` review items are
backfilled into deduplicated ``discovery`` employer-origin candidates.

No network request, connector/source activation, gate execution, Bronze/Silver
write, provider call, scheduler mutation, or application action occurs here.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.stepstone_candidate_persistence import (
    ExistingEmployerCandidate,
    StepStoneCandidatePersistencePlan,
    StepStoneObservedCompany,
    plan_stepstone_candidate_persistence,
)

APPROVAL_TOKEN = "activate_stepstone_baseline_only_and_persist_candidates"
DEFAULT_PROFILE = "stepstone_data_engineer_hannover"
DEFAULT_SEARCH_TERM = "Machine Learning Engineer"
DEFAULT_LOCATION = "Hannover"
DEFAULT_POLICY_VERSION = "stepstone-decoupled-baseline-v1"


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _json_titles(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return (value,) if value.strip() else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def ensure_runtime_schema(conn: psycopg.Connection[Any]) -> None:
    required = (
        "stepstone_runtime_activations",
        "stepstone_candidate_persistence_events",
        "stepstone_company_title_vocabulary",
        "stepstone_baseline_cycle_state",
        "stepstone_filter_suppression_sets",
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY(%s::text[])
            """,
            (list(required),),
        )
        present = {str(row["table_name"]) for row in cur.fetchall()}
    missing = sorted(set(required) - present)
    if missing:
        raise RuntimeError(
            "StepStone runtime schema is incomplete; apply pending migrations first: "
            + ", ".join(missing)
        )


def load_existing_candidates(
    conn: psycopg.Connection[Any],
) -> list[ExistingEmployerCandidate]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, company_key, company_name, status
            FROM employer_origin_source_candidates
            ORDER BY id
            """
        )
        rows = cur.fetchall()
    return [
        ExistingEmployerCandidate(
            candidate_id=int(row["id"]),
            company_key=str(row["company_key"] or ""),
            company_name=str(row["company_name"] or ""),
            status=str(row["status"] or ""),
        )
        for row in rows
    ]


def load_unpersisted_review_observations(
    conn: psycopg.Connection[Any],
    *,
    review_ids: Iterable[int] = (),
) -> list[StepStoneObservedCompany]:
    ids = tuple(dict.fromkeys(int(value) for value in review_ids))
    clauses = [
        "i.item_type = 'observed_company'",
        "p.id IS NULL",
    ]
    params: list[Any] = []
    if ids:
        clauses.append("r.id = ANY(%s::bigint[])")
        params.append(list(ids))

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                r.id AS review_id,
                i.id AS review_item_id,
                r.source_name,
                r.search_profile_name,
                r.search_term,
                r.base_query,
                r.planned_query,
                i.company_key,
                i.company_name,
                i.evidence_count,
                i.sample_titles
            FROM stepstone_company_discovery_cycle_reviews r
            JOIN stepstone_company_discovery_cycle_items i
              ON i.review_id = r.id
            LEFT JOIN stepstone_candidate_persistence_events p
              ON p.review_id = r.id
             AND p.company_key = i.company_key
            WHERE {' AND '.join(clauses)}
            ORDER BY r.id, i.evidence_count DESC, i.company_key
            """,
            params,
        )
        rows = cur.fetchall()

    return [
        StepStoneObservedCompany(
            review_id=int(row["review_id"]),
            review_item_id=(
                int(row["review_item_id"])
                if row["review_item_id"] is not None
                else None
            ),
            source_name=str(row["source_name"]),
            search_profile_name=str(row["search_profile_name"]),
            search_term=str(row["search_term"]),
            company_key=str(row["company_key"] or ""),
            company_name=str(row["company_name"] or ""),
            evidence_count=int(row["evidence_count"] or 0),
            sample_titles=_json_titles(row["sample_titles"]),
            source_mode=(
                "baseline"
                if str(row["planned_query"]) == str(row["base_query"])
                else "filtered"
            ),
        )
        for row in rows
    ]


def create_candidate(
    conn: psycopg.Connection[Any],
    plan: StepStoneCandidatePersistencePlan,
    *,
    persisted_by: str,
) -> int:
    if not plan.create_allowed:
        raise ValueError("create_candidate requires a create-allowed plan")
    observation = plan.observation
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO employer_origin_source_candidates (
                company_key,
                company_name,
                candidate_url,
                source_name_candidate,
                source_family_candidate,
                source_target_candidate,
                source_type_candidate,
                status,
                risk_level,
                notes,
                updated_at
            ) VALUES (
                %s, %s, NULL, %s, %s, NULL, %s,
                'discovery', %s, %s, now()
            )
            RETURNING id
            """,
            (
                plan.normalized_company_key,
                observation.company_name,
                plan.source_name_candidate,
                plan.source_family_candidate,
                plan.source_type_candidate,
                plan.risk_level,
                (
                    "Created from bounded StepStone company observation; "
                    f"review_id={observation.review_id}; "
                    f"evidence_count={observation.evidence_count}; "
                    f"persisted_by={persisted_by}. "
                    "Origin URL intentionally unresolved; no connector or source activated."
                ),
            ),
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("candidate insert returned no id")
    return int(row["id"])


def upsert_title_vocabulary(
    conn: psycopg.Connection[Any],
    *,
    observation: StepStoneObservedCompany,
) -> int:
    count = 0
    with conn.cursor() as cur:
        for raw_title in observation.sample_titles:
            normalized_title = " ".join(raw_title.split()).casefold()
            if not normalized_title:
                continue
            cur.execute(
                """
                INSERT INTO stepstone_company_title_vocabulary (
                    source_name,
                    search_profile_name,
                    search_term,
                    company_key,
                    company_name,
                    raw_title,
                    normalized_title,
                    first_seen_at,
                    last_seen_at,
                    observation_count,
                    job_keys,
                    source_mode
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    now(), now(), 1, '[]'::jsonb, %s
                )
                ON CONFLICT (
                    source_name,
                    search_profile_name,
                    search_term,
                    company_key,
                    normalized_title
                ) DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    raw_title = EXCLUDED.raw_title,
                    last_seen_at = GREATEST(
                        stepstone_company_title_vocabulary.last_seen_at,
                        EXCLUDED.last_seen_at
                    ),
                    observation_count =
                        stepstone_company_title_vocabulary.observation_count + 1,
                    source_mode = EXCLUDED.source_mode,
                    updated_at = now()
                """,
                (
                    observation.source_name,
                    observation.search_profile_name,
                    observation.search_term,
                    plan_company_key(observation),
                    observation.company_name,
                    raw_title,
                    normalized_title,
                    observation.source_mode,
                ),
            )
            count += 1
    return count


def plan_company_key(observation: StepStoneObservedCompany) -> str:
    plan = plan_stepstone_candidate_persistence(observation, ())
    return plan.normalized_company_key


def record_persistence_event(
    conn: psycopg.Connection[Any],
    *,
    plan: StepStoneCandidatePersistencePlan,
    candidate_id: int | None,
    persisted_by: str,
    event_source_mode: str,
) -> None:
    observation = plan.observation
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO stepstone_candidate_persistence_events (
                review_id,
                review_item_id,
                source_name,
                search_profile_name,
                search_term,
                source_mode,
                company_key,
                company_name,
                evidence_count,
                sample_titles,
                candidate_id,
                action,
                reason,
                persisted_by
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s::jsonb, %s, %s, %s, %s
            )
            ON CONFLICT (review_id, company_key) DO NOTHING
            """,
            (
                observation.review_id,
                observation.review_item_id,
                observation.source_name,
                observation.search_profile_name,
                observation.search_term,
                event_source_mode,
                plan.normalized_company_key,
                observation.company_name,
                observation.evidence_count,
                json.dumps(list(observation.sample_titles), ensure_ascii=False),
                candidate_id,
                plan.action,
                plan.reason,
                persisted_by,
            ),
        )


def persist_review_observations(
    conn: psycopg.Connection[Any],
    *,
    observations: Iterable[StepStoneObservedCompany],
    persisted_by: str,
    apply: bool,
    event_source_mode: str = "backfill",
) -> tuple[list[StepStoneCandidatePersistencePlan], int, int, int]:
    existing = load_existing_candidates(conn)
    plans: list[StepStoneCandidatePersistencePlan] = []
    created_count = 0
    matched_count = 0
    vocabulary_count = 0

    for observation in observations:
        plan = plan_stepstone_candidate_persistence(observation, existing)
        candidate_id = plan.matched_candidate_id
        if apply and plan.create_allowed:
            candidate_id = create_candidate(
                conn,
                plan,
                persisted_by=persisted_by,
            )
            created_count += 1
            existing.append(
                ExistingEmployerCandidate(
                    candidate_id=candidate_id,
                    company_key=plan.normalized_company_key,
                    company_name=observation.company_name,
                    status="discovery",
                )
            )
            plan = replace(plan, matched_candidate_id=candidate_id)
        elif plan.action == "matched_existing_candidate":
            matched_count += 1

        if apply:
            vocabulary_count += upsert_title_vocabulary(
                conn,
                observation=observation,
            )
            record_persistence_event(
                conn,
                plan=plan,
                candidate_id=candidate_id,
                persisted_by=persisted_by,
                event_source_mode=event_source_mode,
            )
        plans.append(plan)

    return plans, created_count, matched_count, vocabulary_count


def activate_baseline_only(
    conn: psycopg.Connection[Any],
    *,
    source_name: str,
    search_profile_name: str,
    search_term: str,
    location: str,
    approved_by: str,
    policy_version: str,
    baseline_refresh_interval_hours: int,
    max_filtered_runs_between_baselines: int,
    vocabulary_staleness_hours: int,
    origin_refresh_cooldown_hours: int,
    requested_filter_count: int,
    dominance_min_cards: int,
    dominance_min_share: float,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO stepstone_runtime_activations (
                source_name,
                search_profile_name,
                search_term,
                search_location,
                status,
                control_mode,
                baseline_refresh_interval_hours,
                max_filtered_runs_between_baselines,
                vocabulary_staleness_hours,
                origin_refresh_cooldown_hours,
                requested_filter_count,
                dominance_min_cards,
                dominance_min_share,
                validated_transport_name,
                transport_status,
                approved_max_filter_count,
                policy_version,
                activation_reason,
                approved_by,
                approved_at
            ) VALUES (
                %s, %s, %s, %s,
                'baseline_only_active',
                'decoupled_baseline_filter',
                %s, %s, %s, %s, %s, %s, %s,
                NULL, 'unvalidated', NULL,
                %s, %s, %s, now()
            )
            ON CONFLICT (
                source_name,
                search_profile_name,
                search_term,
                search_location
            ) DO UPDATE SET
                status = 'baseline_only_active',
                control_mode = 'decoupled_baseline_filter',
                baseline_refresh_interval_hours = EXCLUDED.baseline_refresh_interval_hours,
                max_filtered_runs_between_baselines = EXCLUDED.max_filtered_runs_between_baselines,
                vocabulary_staleness_hours = EXCLUDED.vocabulary_staleness_hours,
                origin_refresh_cooldown_hours = EXCLUDED.origin_refresh_cooldown_hours,
                requested_filter_count = EXCLUDED.requested_filter_count,
                dominance_min_cards = EXCLUDED.dominance_min_cards,
                dominance_min_share = EXCLUDED.dominance_min_share,
                validated_transport_name = NULL,
                transport_status = 'unvalidated',
                approved_max_filter_count = NULL,
                policy_version = EXCLUDED.policy_version,
                activation_reason = EXCLUDED.activation_reason,
                approved_by = EXCLUDED.approved_by,
                approved_at = now(),
                paused_at = NULL,
                updated_at = now()
            """,
            (
                source_name,
                search_profile_name,
                search_term,
                location,
                baseline_refresh_interval_hours,
                max_filtered_runs_between_baselines,
                vocabulary_staleness_hours,
                origin_refresh_cooldown_hours,
                requested_filter_count,
                dominance_min_cards,
                dominance_min_share,
                policy_version,
                (
                    "Operator-approved fail-closed production activation: one "
                    "unfiltered page-one baseline per due run; multi-NOT filtering "
                    "remains blocked pending transport and capacity validation."
                ),
                approved_by,
            ),
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-name", default="stepstone")
    parser.add_argument("--search-profile-name", default=DEFAULT_PROFILE)
    parser.add_argument("--search-term", default=DEFAULT_SEARCH_TERM)
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument("--review-id", action="append", type=int, default=[])
    parser.add_argument("--baseline-refresh-hours", type=int, default=24)
    parser.add_argument("--max-filtered-runs", type=int, default=3)
    parser.add_argument("--vocabulary-staleness-hours", type=int, default=168)
    parser.add_argument("--origin-refresh-cooldown-hours", type=int, default=24)
    parser.add_argument("--requested-filter-count", type=int, default=5)
    parser.add_argument("--dominance-min-cards", type=int, default=2)
    parser.add_argument("--dominance-min-share", type=float, default=0.20)
    parser.add_argument("--policy-version", default=DEFAULT_POLICY_VERSION)
    parser.add_argument("--approved-by", default="jens")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit("ABORT: exact --approval-token is required for --apply")

    with connect() as conn:
        ensure_runtime_schema(conn)
        observations = load_unpersisted_review_observations(
            conn,
            review_ids=args.review_id,
        )
        plans, created, matched, vocabulary = persist_review_observations(
            conn,
            observations=observations,
            persisted_by=args.approved_by,
            apply=args.apply,
            event_source_mode="backfill",
        )
        if args.apply:
            activate_baseline_only(
                conn,
                source_name=args.source_name,
                search_profile_name=args.search_profile_name,
                search_term=args.search_term,
                location=args.location,
                approved_by=args.approved_by,
                policy_version=args.policy_version,
                baseline_refresh_interval_hours=args.baseline_refresh_hours,
                max_filtered_runs_between_baselines=args.max_filtered_runs,
                vocabulary_staleness_hours=args.vocabulary_staleness_hours,
                origin_refresh_cooldown_hours=args.origin_refresh_cooldown_hours,
                requested_filter_count=args.requested_filter_count,
                dominance_min_cards=args.dominance_min_cards,
                dominance_min_share=args.dominance_min_share,
            )
            conn.commit()

    print("StepStone baseline runtime activation")
    print(f"apply: {str(args.apply).lower()}")
    print(f"runtime_status: {'baseline_only_active' if args.apply else 'dry_run'}")
    print(f"unpersisted_review_company_count: {len(observations)}")
    print(f"planned_candidate_creation_count: {sum(1 for plan in plans if plan.create_allowed)}")
    print(f"created_candidate_count: {created}")
    print(f"matched_existing_candidate_count: {matched}")
    print(f"title_vocabulary_upsert_count: {vocabulary}")
    print("multi_not_production_status: blocked_pending_transport_and_capacity_validation")
    print("boundary: no StepStone request, no connector/source activation, no scheduler mutation")
    print("RESULT: STEPSTONE_BASELINE_RUNTIME_ACTIVATION_COMPLETED")


if __name__ == "__main__":
    main()
