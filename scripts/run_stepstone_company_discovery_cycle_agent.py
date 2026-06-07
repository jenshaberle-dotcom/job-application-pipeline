"""Run EO-002A3 StepStone Company Discovery Cycle.

Boundary: dry-run first, no pagination, no detail pages, no automatic candidate
creation, no connector activation, no Bronze/Silver write, no scheduler change.

The agent plans a company-discovery cycle for StepStone. It may optionally fetch
one bounded result-card page for due/selected search terms and write review state.
Cooldown application is explicit and separate via --apply-cooldowns.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row
import requests

from src.config import get_database_config
from src.connectors.stepstone import REQUEST_TIMEOUT_SECONDS, USER_AGENT, build_stepstone_search_url
from src.connectors.stepstone_result_cards import extract_result_card_fields
from src.normalization.company_keys import normalize_company_key
from src.search_intelligence.stepstone_company_discovery_cycle import (
    CompanyCooldown,
    CompanyObservation,
    DEFAULT_MAX_NOT_TERMS_PER_REQUEST,
    DEFAULT_NOT_ENABLED_SEARCH_TERMS,
    StepStoneCompanyDiscoveryPlan,
    StepStoneDiscoveryAssessment,
    assess_discovery_observations,
    build_company_discovery_plan,
    company_not_alias,
)


DEFAULT_SOURCE_NAME = "stepstone"


class MissingReviewTables(RuntimeError):
    pass


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _tuple_from_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return tuple(sorted(DEFAULT_NOT_ENABLED_SEARCH_TERMS))
    return tuple(item.strip() for item in value.split(",") if item.strip())


def load_active_stepstone_terms(
    conn: psycopg.Connection[Any],
    *,
    search_profile_name: str,
) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT st.search_term
            FROM search_profiles sp
            JOIN search_terms st
              ON st.search_profile_id = sp.id
            WHERE sp.profile_name = %s
              AND sp.source_name = 'stepstone'
              AND sp.is_active = true
              AND st.is_active = true
            ORDER BY st.id
            """,
            (search_profile_name,),
        )
        rows = cur.fetchall()
    return [str(row["search_term"]) for row in rows]


def ensure_cycle_state(
    conn: psycopg.Connection[Any],
    *,
    source_name: str,
    search_profile_name: str,
    search_terms: list[str],
    enabled_terms: tuple[str, ...],
) -> None:
    with conn.cursor() as cur:
        for search_term in search_terms:
            cur.execute(
                """
                INSERT INTO search_term_cycle_state (
                    source_name,
                    search_profile_name,
                    search_term,
                    is_not_exclusion_enabled,
                    next_due_at
                ) VALUES (%s, %s, %s, %s, now())
                ON CONFLICT (source_name, search_profile_name, search_term)
                DO UPDATE SET
                    is_not_exclusion_enabled = EXCLUDED.is_not_exclusion_enabled,
                    updated_at = now()
                """,
                (
                    source_name,
                    search_profile_name,
                    search_term,
                    search_term.strip().lower() in {term.strip().lower() for term in enabled_terms},
                ),
            )
    conn.commit()


def load_due_terms(
    conn: psycopg.Connection[Any],
    *,
    source_name: str,
    search_profile_name: str,
    limit_search_terms: int,
    force_terms: tuple[str, ...],
) -> list[dict[str, Any]]:
    if force_terms:
        terms = list(force_terms)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    source_name,
                    search_profile_name,
                    search_term,
                    current_interval_days,
                    min_interval_days,
                    max_interval_days,
                    is_not_exclusion_enabled
                FROM search_term_cycle_state
                WHERE source_name = %s
                  AND search_profile_name = %s
                  AND lower(search_term) = ANY(%s::text[])
                ORDER BY search_term
                """,
                (source_name, search_profile_name, [term.lower() for term in terms]),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                source_name,
                search_profile_name,
                search_term,
                current_interval_days,
                min_interval_days,
                max_interval_days,
                is_not_exclusion_enabled
            FROM search_term_cycle_state
            WHERE source_name = %s
              AND search_profile_name = %s
              AND (next_due_at IS NULL OR next_due_at <= now())
            ORDER BY next_due_at NULLS FIRST, search_term
            LIMIT %s
            """,
            (source_name, search_profile_name, limit_search_terms),
        )
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def load_active_company_cooldowns(
    conn: psycopg.Connection[Any],
    *,
    source_name: str,
    search_profile_name: str,
) -> list[CompanyCooldown]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                source_name,
                search_profile_name,
                search_term,
                company_key,
                company_name,
                cooldown_until,
                reason,
                evidence_count
            FROM company_discovery_cooldowns
            WHERE source_name = %s
              AND search_profile_name = %s
              AND cooldown_until > now()
            ORDER BY evidence_count DESC, company_key
            """,
            (source_name, search_profile_name),
        )
        rows = cur.fetchall()
    return [
        CompanyCooldown(
            source_name=str(row["source_name"]),
            search_profile_name=str(row["search_profile_name"]),
            search_term=str(row["search_term"]),
            company_key=str(row["company_key"]),
            company_name=str(row["company_name"]),
            cooldown_until=row["cooldown_until"],
            reason=str(row["reason"]),
            evidence_count=int(row["evidence_count"]),
        )
        for row in rows
    ]


def load_seed_cooldowns_from_known_candidates(
    conn: psycopg.Connection[Any],
    *,
    source_name: str,
    search_profile_name: str,
    search_term: str,
    days: int,
    limit: int,
) -> list[CompanyCooldown]:
    """Build temporary seed cooldowns from known candidates.

    This is not a permanent blacklist. It only gives the first controlled cycle a
    DB-backed set of company blocks to test; persisted cooldowns remain explicit.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH candidates AS (
                SELECT
                    company_key,
                    company_name,
                    status
                FROM employer_origin_source_candidates
                WHERE status IN (
                    'active_controlled',
                    'discovery',
                    'manual_review_required',
                    'abort_documented'
                )
            ), evidence AS (
                SELECT
                    c.company_key,
                    c.company_name,
                    c.status,
                    COUNT(me.id) AS evidence_count
                FROM candidates c
                JOIN market_evidence me
                  ON me.source_name = %s
                 AND lower(me.search_term) = lower(%s)
                 AND (
                      me.normalized_company_key = c.company_key
                      OR starts_with(me.normalized_company_key, c.company_key || '_')
                      OR starts_with(c.company_key, me.normalized_company_key || '_')
                 )
                GROUP BY c.company_key, c.company_name, c.status
            )
            SELECT
                company_key,
                company_name,
                status,
                evidence_count
            FROM evidence
            WHERE evidence_count > 0
            ORDER BY evidence_count DESC, company_key
            LIMIT %s
            """,
            (source_name, search_term, limit),
        )
        rows = cur.fetchall()

    until = datetime.now(UTC) + timedelta(days=days)
    return [
        CompanyCooldown(
            source_name=source_name,
            search_profile_name=search_profile_name,
            search_term=search_term,
            company_key=normalize_company_key(row["company_key"] or row["company_name"]),
            company_name=company_not_alias(
                str(row["company_key"] or row["company_name"]),
                str(row["company_name"]),
            ),
            cooldown_until=until,
            reason=(
                "temporary evidence-weighted seed cooldown "
                f"from known candidate status={row['status']}"
            ),
            evidence_count=int(row["evidence_count"]),
        )
        for row in rows
    ]


def load_seed_cooldowns_from_market_evidence(
    conn: psycopg.Connection[Any],
    *,
    source_name: str,
    search_profile_name: str,
    search_term: str,
    days: int,
    limit: int,
    min_evidence_count: int = 1,
) -> list[CompanyCooldown]:
    """Build a larger temporary seed pool from observed market evidence.

    This is used for read-only/request-wave validation. It intentionally does
    not create candidates and does not make suppression permanent. The logical
    pool may be larger than one request budget so multiple exclusion waves can
    be validated without falling back to duplicate baseline fetches.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                normalized_company_key AS company_key,
                company_name,
                COUNT(*) AS evidence_count
            FROM market_evidence
            WHERE source_name = %s
              AND lower(search_term) = lower(%s)
              AND normalized_company_key IS NOT NULL
              AND normalized_company_key <> ''
              AND company_name IS NOT NULL
              AND company_name <> ''
            GROUP BY normalized_company_key, company_name
            HAVING COUNT(*) >= %s
            ORDER BY COUNT(*) DESC, normalized_company_key
            LIMIT %s
            """,
            (source_name, search_term, min_evidence_count, limit),
        )
        rows = cur.fetchall()

    until = datetime.now(UTC) + timedelta(days=days)
    return [
        CompanyCooldown(
            source_name=source_name,
            search_profile_name=search_profile_name,
            search_term=search_term,
            company_key=normalize_company_key(row["company_key"] or row["company_name"]),
            company_name=company_not_alias(
                str(row["company_key"] or row["company_name"]),
                str(row["company_name"]),
            ),
            cooldown_until=until,
            reason="temporary evidence-weighted seed cooldown from market evidence",
            evidence_count=int(row["evidence_count"]),
        )
        for row in rows
    ]


def fetch_stepstone_observations(plan: StepStoneCompanyDiscoveryPlan) -> tuple[list[CompanyObservation], str]:
    requested_url = build_stepstone_search_url(
        search_term=plan.planned_query,
        search_location="Hannover",
    )
    response = requests.get(
        requested_url,
        headers={
            "User-Agent": USER_AGENT.replace("connector", "company-discovery-cycle-probe"),
            "Accept": "text/html,application/xhtml+xml",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
        allow_redirects=True,
    )
    response.raise_for_status()
    cards = extract_result_card_fields(raw_html=response.text, final_url=response.url)[:25]
    observations = [
        CompanyObservation(
            company_key=normalize_company_key(card.company),
            company_name=card.company or "<missing company>",
            title=card.title or "<missing title>",
            source_url=card.detail_url or response.url,
        )
        for card in cards
        if card.company
    ]
    return observations, response.url


def write_review(
    conn: psycopg.Connection[Any],
    *,
    plan: StepStoneCompanyDiscoveryPlan,
    assessment: StepStoneDiscoveryAssessment,
    observations: list[CompanyObservation],
    reviewed_by: str,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO stepstone_company_discovery_cycle_reviews (
                source_name,
                search_profile_name,
                search_term,
                base_query,
                planned_query,
                action,
                reason,
                observed_count,
                distinct_company_count,
                known_cooldown_hit_count,
                new_company_count,
                relevance_hits,
                drift_hits,
                quality_score,
                recommended_interval_days,
                reviewed_by,
                boundary
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
            )
            RETURNING id
            """,
            (
                plan.source_name,
                plan.search_profile_name,
                plan.search_term,
                plan.base_query,
                plan.planned_query,
                plan.action,
                plan.reason,
                assessment.observed_count,
                assessment.distinct_company_count,
                assessment.known_cooldown_hit_count,
                assessment.new_company_count,
                assessment.relevance_hits,
                assessment.drift_hits,
                assessment.quality_score,
                assessment.recommended_interval_days,
                reviewed_by,
                json.dumps(plan.boundary, sort_keys=True),
            ),
        )
        review_id = int(cur.fetchone()["id"])

        grouped: dict[str, dict[str, object]] = {}
        for observation in observations:
            entry = grouped.setdefault(
                observation.company_key,
                {"company_name": observation.company_name, "count": 0, "titles": []},
            )
            entry["count"] = int(entry["count"]) + 1
            titles = entry["titles"]
            if isinstance(titles, list) and observation.title not in titles and len(titles) < 5:
                titles.append(observation.title)

        for company_key, entry in grouped.items():
            cur.execute(
                """
                INSERT INTO stepstone_company_discovery_cycle_items (
                    review_id,
                    item_type,
                    company_key,
                    company_name,
                    evidence_count,
                    sample_titles,
                    reason
                ) VALUES (%s, 'observed_company', %s, %s, %s, %s::jsonb, %s)
                """,
                (
                    review_id,
                    company_key,
                    entry["company_name"],
                    int(entry["count"]),
                    json.dumps(entry["titles"], ensure_ascii=False),
                    "observed during bounded StepStone company-discovery cycle",
                ),
            )

        for proposal in assessment.cooldown_proposals:
            cooldown_until = datetime.now(UTC) + timedelta(days=proposal.cooldown_days)
            cur.execute(
                """
                INSERT INTO stepstone_company_discovery_cycle_items (
                    review_id,
                    item_type,
                    company_key,
                    company_name,
                    evidence_count,
                    sample_titles,
                    reason,
                    cooldown_until
                ) VALUES (%s, 'cooldown_proposal', %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (
                    review_id,
                    proposal.company_key,
                    proposal.company_name,
                    proposal.evidence_count,
                    json.dumps(list(proposal.sample_titles), ensure_ascii=False),
                    proposal.reason,
                    cooldown_until,
                ),
            )

    conn.commit()
    return review_id


def apply_cooldowns_from_review(conn: psycopg.Connection[Any], *, review_id: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO company_discovery_cooldowns (
                source_name,
                search_profile_name,
                search_term,
                company_key,
                company_name,
                cooldown_until,
                reason,
                evidence_count,
                learned_title_count,
                created_by_review_id
            )
            SELECT
                r.source_name,
                r.search_profile_name,
                r.search_term,
                i.company_key,
                i.company_name,
                i.cooldown_until,
                i.reason,
                i.evidence_count,
                jsonb_array_length(i.sample_titles),
                r.id
            FROM stepstone_company_discovery_cycle_reviews r
            JOIN stepstone_company_discovery_cycle_items i
              ON i.review_id = r.id
            WHERE r.id = %s
              AND i.item_type = 'cooldown_proposal'
              AND i.cooldown_until IS NOT NULL
            """,
            (review_id,),
        )
        count = cur.rowcount
    conn.commit()
    return int(count)


def update_cycle_state_after_review(
    conn: psycopg.Connection[Any],
    *,
    plan: StepStoneCompanyDiscoveryPlan,
    assessment: StepStoneDiscoveryAssessment,
) -> None:
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
                updated_at = now()
            WHERE source_name = %s
              AND search_profile_name = %s
              AND search_term = %s
            """,
            (
                assessment.recommended_interval_days,
                assessment.recommended_interval_days,
                assessment.quality_score,
                assessment.new_company_count,
                assessment.known_cooldown_hit_count,
                plan.source_name,
                plan.search_profile_name,
                plan.search_term,
            ),
        )
    conn.commit()


def render_result(
    *,
    plan: StepStoneCompanyDiscoveryPlan,
    assessment: StepStoneDiscoveryAssessment | None,
    observations: list[CompanyObservation],
    final_url: str | None,
    persisted_review_id: int | None,
) -> None:
    print("---")
    print(f"search_term: {plan.search_term}")
    print(f"action: {plan.action}")
    print(f"reason: {plan.reason}")
    print(f"planned_query: {plan.planned_query}")
    print(f"not_company_names: {', '.join(plan.not_company_names) if plan.not_company_names else '-'}")
    print(f"cooldown_pool_size: {plan.boundary.get('cooldown_pool_size', '-')}")
    print(f"selected_wave_size: {plan.boundary.get('selected_wave_size', '-')}")
    print(f"wave_start_index: {plan.boundary.get('wave_start_index', '-')}")
    print(f"wave_end_index: {plan.boundary.get('wave_end_index', '-')}")
    if final_url:
        print(f"final_url: {final_url}")
    print(f"persisted_review_id: {persisted_review_id if persisted_review_id else '-'}")

    if assessment is None:
        print("assessment: not fetched")
        return

    print(f"observed_count: {assessment.observed_count}")
    print(f"distinct_company_count: {assessment.distinct_company_count}")
    print(f"known_cooldown_hit_count: {assessment.known_cooldown_hit_count}")
    print(f"new_company_count: {assessment.new_company_count}")
    print(f"relevance_hits: {assessment.relevance_hits}")
    print(f"drift_hits: {assessment.drift_hits}")
    print(f"quality_score: {assessment.quality_score}")
    print(f"recommended_interval_days: {assessment.recommended_interval_days}")

    print("observed_companies:")
    counts: dict[str, int] = {}
    names: dict[str, str] = {}
    for observation in observations:
        counts[observation.company_key] = counts.get(observation.company_key, 0) + 1
        names[observation.company_key] = observation.company_name
    for company_key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:20]:
        print(f"- {company_key} | {names[company_key]} | evidence_count={count}")

    print("cooldown_proposals:")
    if not assessment.cooldown_proposals:
        print("- none")
    for proposal in assessment.cooldown_proposals[:20]:
        print(
            f"- {proposal.company_key} | {proposal.company_name} | "
            f"evidence_count={proposal.evidence_count} | cooldown_days={proposal.cooldown_days}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-name", default=DEFAULT_SOURCE_NAME)
    parser.add_argument("--search-profile-name", default="stepstone_data_engineer_hannover")
    parser.add_argument("--enabled-not-terms", default=None, help="Comma-separated whitelist. Defaults to Data Engineer,Analytics Engineer.")
    parser.add_argument("--limit-search-terms", type=int, default=2)
    parser.add_argument("--force-search-term", action="append", default=[])
    parser.add_argument(
        "--max-not-terms-per-request",
        type=int,
        default=DEFAULT_MAX_NOT_TERMS_PER_REQUEST,
        help="Request budget only; the logical company-cooldown pool is not capped.",
    )
    parser.add_argument(
        "--exclusion-wave-index",
        type=int,
        default=0,
        help="Select a bounded request window from the prioritized cooldown pool.",
    )
    parser.add_argument("--max-not-companies", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--seed-known-candidates", action="store_true", help="Use known candidates as temporary seed cooldowns for this dry-run/review.")
    parser.add_argument(
        "--seed-market-evidence-companies",
        action="store_true",
        help="Use observed market-evidence companies as a larger temporary seed pool for request-wave validation.",
    )
    parser.add_argument("--seed-cooldown-days", type=int, default=7)
    parser.add_argument(
        "--seed-candidate-limit",
        type=int,
        default=50,
        help="Known-candidate seed pool safety limit; not the per-request NOT budget.",
    )
    parser.add_argument(
        "--seed-market-evidence-limit",
        type=int,
        default=80,
        help="Market-evidence seed pool safety limit; not the per-request NOT budget.",
    )
    parser.add_argument("--fetch", action="store_true", help="Fetch one bounded StepStone result-card page per selected term.")
    parser.add_argument("--write-review-state", action="store_true", help="Persist review state only; no cooldown application unless --apply-cooldowns is also set.")
    parser.add_argument("--apply-cooldowns", action="store_true", help="Apply cooldown proposals from the written review state.")
    parser.add_argument("--review-id", type=int, help="Apply cooldowns from an existing review id and exit.")
    parser.add_argument("--reviewed-by", default="agent")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    enabled_terms = _tuple_from_csv(args.enabled_not_terms)

    print("EO-002A3 StepStone Company Discovery Cycle")
    print("boundary: dry-run first, no pagination, no detail pages, no automatic candidate creation, no connector activation, no Bronze/Silver write, no scheduler change")
    print(f"source_name: {args.source_name}")
    print(f"search_profile_name: {args.search_profile_name}")
    print(f"enabled_not_terms: {', '.join(enabled_terms)}")
    print(f"fetch_mode: {str(args.fetch).lower()}")
    print(f"write_review_state: {str(args.write_review_state).lower()}")
    print(f"apply_cooldowns: {str(args.apply_cooldowns).lower()}")

    max_not_terms_per_request = (
        args.max_not_companies
        if args.max_not_companies is not None
        else args.max_not_terms_per_request
    )
    print(f"max_not_terms_per_request: {max_not_terms_per_request}")
    print(f"exclusion_wave_index: {args.exclusion_wave_index}")
    print(f"seed_market_evidence_companies: {str(args.seed_market_evidence_companies).lower()}")

    with connect() as conn:
        if args.review_id:
            if not args.apply_cooldowns:
                raise SystemExit("--review-id requires --apply-cooldowns")
            applied = apply_cooldowns_from_review(conn, review_id=args.review_id)
            print(f"applied_cooldown_count: {applied}")
            return

        search_terms = load_active_stepstone_terms(conn, search_profile_name=args.search_profile_name)
        ensure_cycle_state(
            conn,
            source_name=args.source_name,
            search_profile_name=args.search_profile_name,
            search_terms=search_terms,
            enabled_terms=enabled_terms,
        )
        due_terms = load_due_terms(
            conn,
            source_name=args.source_name,
            search_profile_name=args.search_profile_name,
            limit_search_terms=args.limit_search_terms,
            force_terms=tuple(args.force_search_term),
        )

        if not due_terms:
            print("No due search terms found.")
            return

        base_cooldowns = load_active_company_cooldowns(
            conn,
            source_name=args.source_name,
            search_profile_name=args.search_profile_name,
        )

        for row in due_terms:
            search_term = str(row["search_term"])
            cooldowns = list(base_cooldowns)
            if args.seed_known_candidates:
                cooldowns.extend(
                    load_seed_cooldowns_from_known_candidates(
                        conn,
                        source_name=args.source_name,
                        search_profile_name=args.search_profile_name,
                        search_term=search_term,
                        days=args.seed_cooldown_days,
                        limit=args.seed_candidate_limit,
                    )
                )
            if args.seed_market_evidence_companies:
                cooldowns.extend(
                    load_seed_cooldowns_from_market_evidence(
                        conn,
                        source_name=args.source_name,
                        search_profile_name=args.search_profile_name,
                        search_term=search_term,
                        days=args.seed_cooldown_days,
                        limit=args.seed_market_evidence_limit,
                    )
                )

            plan = build_company_discovery_plan(
                source_name=args.source_name,
                search_profile_name=args.search_profile_name,
                search_term=search_term,
                cooldowns=cooldowns,
                enabled_terms=enabled_terms,
                max_not_terms_per_request=max_not_terms_per_request,
                exclusion_wave_index=args.exclusion_wave_index,
            )

            observations: list[CompanyObservation] = []
            final_url: str | None = None
            assessment: StepStoneDiscoveryAssessment | None = None
            persisted_review_id: int | None = None

            if args.fetch and plan.action != "skip_empty_exclusion_wave":
                observations, final_url = fetch_stepstone_observations(plan)
                assessment = assess_discovery_observations(
                    search_term=search_term,
                    observations=observations,
                    cooldown_company_keys=plan.not_company_keys,
                    current_interval_days=int(row["current_interval_days"]),
                    min_interval_days=int(row["min_interval_days"]),
                    max_interval_days=int(row["max_interval_days"]),
                )

            if args.write_review_state:
                if assessment is None:
                    assessment = assess_discovery_observations(
                        search_term=search_term,
                        observations=[],
                        cooldown_company_keys=plan.not_company_keys,
                        current_interval_days=int(row["current_interval_days"]),
                        min_interval_days=int(row["min_interval_days"]),
                        max_interval_days=int(row["max_interval_days"]),
                    )
                persisted_review_id = write_review(
                    conn,
                    plan=plan,
                    assessment=assessment,
                    observations=observations,
                    reviewed_by=args.reviewed_by,
                )
                update_cycle_state_after_review(conn, plan=plan, assessment=assessment)
                if args.apply_cooldowns:
                    applied = apply_cooldowns_from_review(conn, review_id=persisted_review_id)
                    print(f"applied_cooldown_count_for_review_{persisted_review_id}: {applied}")

            render_result(
                plan=plan,
                assessment=assessment,
                observations=observations,
                final_url=final_url,
                persisted_review_id=persisted_review_id,
            )


if __name__ == "__main__":
    main()
