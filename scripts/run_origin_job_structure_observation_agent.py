"""Run adaptive origin job-page observation.

This agent is a learning-input step only. It observes heterogeneous job pages,
extracts structural/signal candidates and stops dynamically when marginal
learning value saturates. It does not update candidate gates, candidate status,
connectors, Bronze/Silver data or scheduler configuration.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row
import requests

from src.config import get_database_config
from src.search_intelligence.origin_job_observation import (
    OBSERVATION_BOUNDARY,
    AdaptiveObservationLoop,
    JobPageObservation,
    ObservationConfig,
    PageObservationInput,
    build_observation,
    canonical_url_key,
    decide_seed_observation,
    extract_job_like_urls,
    normalize_text,
    summarize_learning_values,
)
from src.search_intelligence.origin_seed_pool import (
    ObservationSeed,
    classify_seed_row,
    deduplicate_seeds,
    observation_url_seeds,
    seed_type_counts,
)

USER_AGENT = "job-application-pipeline-origin-observation/0.1 (+bounded personal portfolio project)"


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def load_known_patterns(conn: psycopg.Connection[Any]) -> set[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pattern_type, pattern_value
            FROM origin_observed_pattern_candidates
            WHERE promotion_status IN ('observed', 'candidate', 'promoted')
            """
        )
        rows = cur.fetchall()
    return {(str(row["pattern_type"]), normalize_text(row["pattern_value"])) for row in rows}


def load_known_observed_url_keys(conn: psycopg.Connection[Any]) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_url, final_url
            FROM origin_job_page_observations
            WHERE source_url IS NOT NULL
            """
        )
        rows = cur.fetchall()
    keys: set[str] = set()
    for row in rows:
        for value in (row["source_url"], row["final_url"]):
            if value:
                keys.add(canonical_url_key(str(value)))
    return keys


def load_saturated_hosts(
    conn: psycopg.Connection[Any],
    *,
    min_observations: int,
    low_value_threshold: float,
) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT host,
                   COUNT(*) AS observation_count,
                   AVG(learning_value) AS avg_learning_value,
                   MAX(learning_value) AS max_learning_value
            FROM origin_job_page_observations
            WHERE host IS NOT NULL
            GROUP BY host
            HAVING COUNT(*) >= %s
               AND AVG(learning_value) < %s
               AND MAX(learning_value) < 0.35
            """,
            (min_observations, low_value_threshold),
        )
        rows = cur.fetchall()
    return {str(row["host"]).lower() for row in rows if row["host"]}


def _table_columns(conn: psycopg.Connection[Any], table_name: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            """,
            (table_name,),
        )
        return {str(row["column_name"]) for row in cur.fetchall()}


def _table_exists(conn: psycopg.Connection[Any], table_name: str) -> bool:
    return bool(_table_columns(conn, table_name))


def load_observation_seeds(
    conn: psycopg.Connection[Any],
    *,
    company_key: str | None,
    limit: int,
    include_expanded_seed_pool: bool,
) -> list[ObservationSeed]:
    rows: list[dict[str, object]] = []
    params: list[object] = []
    company_filter = ""
    if company_key:
        company_filter = " AND company_key = %s"
        params.append(company_key)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                'employer_origin_source_candidates' AS seed_source_table,
                company_key,
                company_name,
                source_name_candidate AS source_name,
                source_family_candidate,
                candidate_url AS seed_url,
                status
            FROM employer_origin_source_candidates
            WHERE (candidate_url IS NOT NULL OR company_name IS NOT NULL)
              {company_filter}
            ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
            LIMIT %s
            """,
            tuple(params + [limit]),
        )
        rows.extend(dict(row) for row in cur.fetchall())

    if _table_exists(conn, "employer_origin_job_detail_evidence"):
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    'employer_origin_job_detail_evidence' AS seed_source_table,
                    company_key,
                    company_key AS company_name,
                    company_key AS source_family_candidate,
                    COALESCE(final_url, source_url) AS seed_url,
                    relevance_decision AS status
                FROM employer_origin_job_detail_evidence
                WHERE COALESCE(final_url, source_url) IS NOT NULL
                  {company_filter}
                ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
                LIMIT %s
                """,
                tuple(params + [limit]),
            )
            rows.extend(dict(row) for row in cur.fetchall())

    if include_expanded_seed_pool and not company_key:
        optional_queries = [
            (
                "candidate_promotion_review_items",
                """
                SELECT
                    'candidate_promotion_review_items' AS seed_source_table,
                    company_key,
                    company_name,
                    source_name,
                    source_family_candidate,
                    candidate_url AS seed_url,
                    source_decision AS status
                FROM candidate_promotion_review_items
                ORDER BY created_candidate_id DESC NULLS LAST, company_name
                LIMIT %s
                """,
            ),
            (
                "candidate_expansion_review_items",
                """
                SELECT
                    'candidate_expansion_review_items' AS seed_source_table,
                    company_key,
                    company_name,
                    source_name,
                    NULL::text AS seed_url,
                    distinct_search_term_count
                FROM candidate_expansion_review_items
                ORDER BY distinct_search_term_count DESC NULLS LAST, company_name
                LIMIT %s
                """,
            ),
            (
                "aggregator_novelty_items",
                """
                SELECT
                    'aggregator_novelty_items' AS seed_source_table,
                    company_key,
                    company_name,
                    source_name,
                    evidence_url AS seed_url,
                    search_term
                FROM aggregator_novelty_items
                ORDER BY company_name
                LIMIT %s
                """,
            ),
            (
                "market_evidence",
                """
                SELECT
                    'market_evidence' AS seed_source_table,
                    normalized_company_key AS company_key,
                    company_name,
                    source_name,
                    evidence_url AS seed_url,
                    search_term
                FROM market_evidence
                ORDER BY source_seen_at DESC NULLS LAST, company_name
                LIMIT %s
                """,
            ),
            (
                "raw_jobs",
                """
                SELECT DISTINCT
                    'raw_jobs' AS seed_source_table,
                    NULL::text AS company_key,
                    NULL::text AS company_name,
                    source_name,
                    source_url AS seed_url
                FROM raw_jobs
                WHERE source_url IS NOT NULL
                  AND btrim(source_url) <> ''
                ORDER BY source_name, source_url
                LIMIT %s
                """,
            ),
        ]
        for table_name, query in optional_queries:
            if not _table_exists(conn, table_name):
                continue
            with conn.cursor() as cur:
                cur.execute(query, (limit,))
                rows.extend(dict(row) for row in cur.fetchall())
        if _table_exists(conn, "silver_jobs") and "company_name" in _table_columns(conn, "silver_jobs"):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        'silver_jobs' AS seed_source_table,
                        normalized_company_name AS company_key,
                        company_name,
                        source_name,
                        source_url AS seed_url,
                        COUNT(*) AS silver_job_count
                    FROM silver_jobs
                    WHERE company_name IS NOT NULL
                      AND btrim(company_name) <> ''
                    GROUP BY normalized_company_name, company_name, source_name, source_url
                    ORDER BY COUNT(*) DESC, company_name
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows.extend(dict(row) for row in cur.fetchall())

    return deduplicate_seeds(classify_seed_row(row) for row in rows)


def create_run(
    conn: psycopg.Connection[Any],
    *,
    config: ObservationConfig,
    source_scope: str,
    created_by: str,
    seed_source_type_counts: dict[str, int] | None = None,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO origin_job_observation_runs (
                source_scope,
                min_observations,
                soft_cap,
                hard_cap,
                boundary,
                created_by,
                seed_source_type_counts
            )
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s::jsonb)
            RETURNING id
            """,
            (
                source_scope,
                config.min_observations,
                config.soft_cap,
                config.hard_cap,
                json.dumps(OBSERVATION_BOUNDARY, sort_keys=True),
                created_by,
                json.dumps(seed_source_type_counts or {}, sort_keys=True),
            ),
        )
        run_id = int(cur.fetchone()["id"])
    conn.commit()
    return run_id




def update_run_local_host_saturation(
    saturated_hosts: set[str],
    host_low_value_counts: dict[str, int],
    *,
    host: str | None,
    learning_value: float,
    min_observations: int,
    low_value_threshold: float,
) -> bool:
    """Mark hosts saturated within a run after repeated low-value observations.

    Historical saturation is loaded before a run starts, but defensive observation
    should also stop wasting budget when a newly encountered provider produces a
    sequence of low-value pages during the current run. This is learning-input
    bookkeeping only; it does not affect candidate gates or source status.
    """

    if not host:
        return False
    normalized_host = host.lower()
    if learning_value < low_value_threshold:
        host_low_value_counts[normalized_host] = host_low_value_counts.get(normalized_host, 0) + 1
    else:
        host_low_value_counts[normalized_host] = 0
    if host_low_value_counts[normalized_host] >= min_observations:
        saturated_hosts.add(normalized_host)
        return True
    return False


def fetch_observation_input(url: str, *, source_family: str | None, timeout_seconds: float) -> PageObservationInput:
    try:
        response = requests.get(
            url,
            timeout=timeout_seconds,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            allow_redirects=True,
        )
        return PageObservationInput(
            source_url=url,
            final_url=str(response.url or url),
            status_code=int(response.status_code or 0),
            title=None,
            body=response.text or "",
            source_family_guess=source_family,
        )
    except requests.RequestException as exc:
        return PageObservationInput(
            source_url=url,
            final_url=url,
            status_code=None,
            title="request failed",
            body=f"request_failed {type(exc).__name__}: {exc}",
            source_family_guess=source_family,
        )


def _json_array(values: Iterable[str]) -> str:
    return json.dumps(list(values), sort_keys=True)


def persist_observation(
    cur: psycopg.Cursor[Any],
    *,
    run_id: int,
    observation: JobPageObservation,
) -> int | None:
    if observation.storage_class == "discard_after_run":
        return None
    cur.execute(
        """
        INSERT INTO origin_job_page_observations (
            run_id,
            source_url,
            final_url,
            host,
            source_family_guess,
            status_code,
            page_type_guess,
            title,
            ats_family_guess,
            has_json_ld_jobposting,
            visible_job_link_count,
            detail_url_patterns,
            location_signal_candidates,
            remote_signal_candidates,
            profile_signal_candidates,
            structural_markers,
            learning_value,
            novelty_reasons,
            storage_class,
            observation_summary,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
            %s, %s::jsonb, %s, %s::jsonb, now()
        )
        ON CONFLICT (run_id, source_url)
        DO UPDATE SET
            final_url = EXCLUDED.final_url,
            host = EXCLUDED.host,
            source_family_guess = EXCLUDED.source_family_guess,
            status_code = EXCLUDED.status_code,
            page_type_guess = EXCLUDED.page_type_guess,
            title = EXCLUDED.title,
            ats_family_guess = EXCLUDED.ats_family_guess,
            has_json_ld_jobposting = EXCLUDED.has_json_ld_jobposting,
            visible_job_link_count = EXCLUDED.visible_job_link_count,
            detail_url_patterns = EXCLUDED.detail_url_patterns,
            location_signal_candidates = EXCLUDED.location_signal_candidates,
            remote_signal_candidates = EXCLUDED.remote_signal_candidates,
            profile_signal_candidates = EXCLUDED.profile_signal_candidates,
            structural_markers = EXCLUDED.structural_markers,
            learning_value = EXCLUDED.learning_value,
            novelty_reasons = EXCLUDED.novelty_reasons,
            storage_class = EXCLUDED.storage_class,
            observation_summary = EXCLUDED.observation_summary,
            updated_at = now()
        RETURNING id
        """,
        (
            run_id,
            observation.source_url,
            observation.final_url,
            observation.host,
            observation.source_family_guess,
            observation.status_code,
            observation.page_type_guess,
            observation.title,
            observation.ats_family_guess,
            observation.has_json_ld_jobposting,
            observation.visible_job_link_count,
            _json_array(observation.detail_url_patterns),
            _json_array(observation.location_signal_candidates),
            _json_array(observation.remote_signal_candidates),
            _json_array(observation.profile_signal_candidates),
            _json_array(observation.structural_markers),
            observation.learning_value,
            _json_array(observation.novelty_reasons),
            observation.storage_class,
            json.dumps(observation.summary, sort_keys=True),
        ),
    )
    row = cur.fetchone()
    return int(row["id"]) if row else None


def persist_pattern_candidates(
    cur: psycopg.Cursor[Any],
    *,
    run_id: int,
    observation_id: int | None,
    observation: JobPageObservation,
) -> None:
    if observation_id is None:
        return
    for pattern_type, pattern_value in observation.pattern_candidates:
        cur.execute(
            """
            INSERT INTO origin_observed_pattern_candidates (
                pattern_type,
                pattern_value,
                evidence_count,
                first_seen_run_id,
                last_seen_run_id,
                first_seen_observation_id,
                last_seen_observation_id,
                confidence,
                learning_notes,
                evidence,
                updated_at
            )
            VALUES (%s, %s, 1, %s, %s, %s, %s, %s, %s, %s::jsonb, now())
            ON CONFLICT (pattern_type, pattern_value)
            DO UPDATE SET
                evidence_count = origin_observed_pattern_candidates.evidence_count + 1,
                last_seen_run_id = EXCLUDED.last_seen_run_id,
                last_seen_observation_id = EXCLUDED.last_seen_observation_id,
                confidence = LEAST(0.95, origin_observed_pattern_candidates.confidence + 0.03),
                evidence = EXCLUDED.evidence,
                updated_at = now()
            """,
            (
                pattern_type,
                pattern_value,
                run_id,
                run_id,
                observation_id,
                observation_id,
                min(0.95, max(0.4, observation.learning_value)),
                "Observed by adaptive origin job observation loop; learning input only.",
                json.dumps(observation.summary, sort_keys=True),
            ),
        )


def finish_run(
    conn: psycopg.Connection[Any],
    *,
    run_id: int,
    loop: AdaptiveObservationLoop,
    observations: list[JobPageObservation],
    skipped_duplicate_url_count: int,
    skipped_known_url_count: int,
    skipped_saturated_host_count: int,
    skipped_by_policy_counts: dict[str, int] | None = None,
    observed_by_source_type_counts: dict[str, int] | None = None,
    learning_value_by_source_type: dict[str, float] | None = None,
) -> None:
    summary = summarize_learning_values([observation.learning_value for observation in observations])
    full_count = sum(1 for observation in observations if observation.storage_class == "full_observation")
    summary_count = sum(1 for observation in observations if observation.storage_class == "summary_only")
    discard_count = sum(1 for observation in observations if observation.storage_class == "discard_after_run")
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE origin_job_observation_runs
            SET observed_page_count = %s,
                stored_full_observation_count = %s,
                summary_only_count = %s,
                discarded_count = %s,
                skipped_duplicate_url_count = %s,
                skipped_known_url_count = %s,
                skipped_saturated_host_count = %s,
                total_learning_value = %s,
                max_learning_value = %s,
                stop_reason = %s,
                skipped_by_policy_counts = %s::jsonb,
                observed_by_source_type_counts = %s::jsonb,
                learning_value_by_source_type = %s::jsonb,
                finished_at = now(),
                updated_at = now()
            WHERE id = %s
            """,
            (
                int(summary["count"]),
                full_count,
                summary_count,
                discard_count,
                skipped_duplicate_url_count,
                skipped_known_url_count,
                skipped_saturated_host_count,
                summary["total"],
                summary["max"],
                loop.stop_reason or "seed_exhausted",
                json.dumps(skipped_by_policy_counts or {}, sort_keys=True),
                json.dumps(observed_by_source_type_counts or {}, sort_keys=True),
                json.dumps(learning_value_by_source_type or {}, sort_keys=True),
                run_id,
            ),
        )
    conn.commit()


def run(args: argparse.Namespace) -> int:
    config = ObservationConfig(
        min_observations=args.min_observations,
        soft_cap=args.soft_cap,
        hard_cap=args.hard_cap,
        saturation_window=args.saturation_window,
    )
    with connect() as conn:
        all_seeds = load_observation_seeds(
            conn,
            company_key=args.company_key,
            limit=args.seed_limit,
            include_expanded_seed_pool=args.include_expanded_seed_pool,
        )
        seeds = observation_url_seeds(all_seeds)
        known_patterns = load_known_patterns(conn)
        known_url_keys = set() if args.revalidate_known_seeds else load_known_observed_url_keys(conn)
        saturated_hosts = (
            set()
            if args.revalidate_known_seeds
            else load_saturated_hosts(
                conn,
                min_observations=args.host_saturation_min_observations,
                low_value_threshold=args.host_saturation_low_value_threshold,
            )
        )
        run_id = create_run(
            conn,
            config=config,
            source_scope="company_key=" + args.company_key if args.company_key else "employer_origin_candidates",
            created_by=args.reviewed_by,
            seed_source_type_counts=seed_type_counts(all_seeds),
        )

    loop = AdaptiveObservationLoop(config=config)
    observations: list[JobPageObservation] = []
    queue: list[tuple[str, str | None, str]] = [
        (str(seed.seed_url), seed.source_family or seed.company_key, seed.seed_type)
        for seed in seeds
        if seed.seed_url
    ]
    seen_url_keys: set[str] = set()
    host_observation_counts: dict[str, int] = {}
    host_low_value_counts: dict[str, int] = {}
    skipped_duplicate_url_count = 0
    skipped_known_url_count = 0
    skipped_saturated_host_count = 0
    skipped_by_policy_counts: dict[str, int] = {}
    observed_by_source_type_counts: dict[str, int] = {}
    learning_value_by_source_type: dict[str, float] = {}
    index = 0

    while index < len(queue) and loop.observed_count < config.hard_cap:
        url, source_family, seed_type = queue[index]
        index += 1

        decision = decide_seed_observation(
            url,
            seen_url_keys=seen_url_keys,
            known_url_keys=known_url_keys,
            saturated_hosts=saturated_hosts,
            saturated_host_counts=host_observation_counts,
            saturated_host_budget=args.saturated_host_budget,
            revalidate_known=args.revalidate_known_seeds,
        )
        if not decision.should_observe:
            if decision.reason == "duplicate_in_run":
                skipped_duplicate_url_count += 1
            elif decision.reason == "known_seed_url":
                skipped_known_url_count += 1
            elif decision.reason == "saturated_provider_host":
                skipped_saturated_host_count += 1
            skipped_by_policy_counts[decision.reason] = skipped_by_policy_counts.get(decision.reason, 0) + 1
            print(f"skip_seed: url={url} | seed_type={seed_type} | reason={decision.reason}")
            continue

        seen_url_keys.add(decision.url_key)
        if decision.host:
            host_observation_counts[decision.host] = host_observation_counts.get(decision.host, 0) + 1

        raw = fetch_observation_input(url, source_family=source_family, timeout_seconds=args.timeout_seconds)
        observation = build_observation(raw, known_patterns=known_patterns)
        observations.append(observation)
        loop.record(observation)
        observed_by_source_type_counts[seed_type] = observed_by_source_type_counts.get(seed_type, 0) + 1
        learning_value_by_source_type[seed_type] = round(
            learning_value_by_source_type.get(seed_type, 0.0) + float(observation.learning_value),
            4,
        )
        known_patterns.update((pattern_type, normalize_text(value)) for pattern_type, value in observation.pattern_candidates)
        update_run_local_host_saturation(
            saturated_hosts,
            host_low_value_counts,
            host=observation.host,
            learning_value=observation.learning_value,
            min_observations=args.host_saturation_min_observations,
            low_value_threshold=args.host_saturation_low_value_threshold,
        )

        for discovered_url in extract_job_like_urls(base_url=raw.final_url or raw.source_url, body=raw.body, max_links=args.max_discovered_links_per_page):
            if len(queue) >= args.seed_limit:
                break
            discovered_decision = decide_seed_observation(
                discovered_url,
                seen_url_keys=seen_url_keys | {canonical_url_key(queued_url) for queued_url, _, _ in queue[index:]},
                known_url_keys=known_url_keys,
                saturated_hosts=saturated_hosts,
                saturated_host_counts=host_observation_counts,
                saturated_host_budget=args.saturated_host_budget,
                revalidate_known=args.revalidate_known_seeds,
            )
            if not discovered_decision.should_observe:
                if discovered_decision.reason == "duplicate_in_run":
                    skipped_duplicate_url_count += 1
                elif discovered_decision.reason == "known_seed_url":
                    skipped_known_url_count += 1
                elif discovered_decision.reason == "saturated_provider_host":
                    skipped_saturated_host_count += 1
                continue
            queue.append((discovered_url, source_family, "discovered_url_seed"))

        with connect() as conn:
            with conn.cursor() as cur:
                observation_id = persist_observation(cur, run_id=run_id, observation=observation)
                persist_pattern_candidates(cur, run_id=run_id, observation_id=observation_id, observation=observation)
            conn.commit()

        print(
            "observation: "
            f"url={observation.source_url} | storage={observation.storage_class} | "
            f"value={observation.learning_value} | type={observation.page_type_guess} | "
            f"reasons={list(observation.novelty_reasons)}"
        )
        if not loop.should_continue():
            break

    if not observations and (skipped_known_url_count or skipped_saturated_host_count or skipped_duplicate_url_count):
        loop.stop_reason = "known_seed_saturation"

    with connect() as conn:
        finish_run(
            conn,
            run_id=run_id,
            loop=loop,
            observations=observations,
            skipped_duplicate_url_count=skipped_duplicate_url_count,
            skipped_known_url_count=skipped_known_url_count,
            skipped_saturated_host_count=skipped_saturated_host_count,
            skipped_by_policy_counts=skipped_by_policy_counts,
            observed_by_source_type_counts=observed_by_source_type_counts,
            learning_value_by_source_type=learning_value_by_source_type,
        )

    summary = summarize_learning_values([observation.learning_value for observation in observations])
    print(f"observation_run_id: {run_id}")
    print(f"observed_page_count: {summary['count']}")
    print(f"total_learning_value: {summary['total']}")
    print(f"max_learning_value: {summary['max']}")
    print(f"skipped_duplicate_url_count: {skipped_duplicate_url_count}")
    print(f"skipped_known_url_count: {skipped_known_url_count}")
    print(f"skipped_saturated_host_count: {skipped_saturated_host_count}")
    print(f"seed_source_type_counts: {json.dumps(seed_type_counts(all_seeds), sort_keys=True)}")
    print(f"observed_by_source_type_counts: {json.dumps(observed_by_source_type_counts, sort_keys=True)}")
    print(f"learning_value_by_source_type: {json.dumps(learning_value_by_source_type, sort_keys=True)}")
    print(f"skipped_by_policy_counts: {json.dumps(skipped_by_policy_counts, sort_keys=True)}")
    print(f"stop_reason: {loop.stop_reason or 'seed_exhausted'}")
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run adaptive origin job-page observation as learning input only.")
    parser.add_argument("--company-key", default=None)
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--seed-limit", type=int, default=100)
    parser.add_argument("--include-expanded-seed-pool", action="store_true", help="Include bounded non-origin seed sources such as ATS/raw/market/company-name seeds with source-type boundaries.")
    parser.add_argument("--max-discovered-links-per-page", type=int, default=8)
    parser.add_argument("--min-observations", type=int, default=20)
    parser.add_argument("--soft-cap", type=int, default=40)
    parser.add_argument("--hard-cap", type=int, default=75)
    parser.add_argument("--saturation-window", type=int, default=5)
    parser.add_argument("--revalidate-known-seeds", action="store_true", help="Fetch known URLs again as bounded drift/revalidation, not normal learning.")
    parser.add_argument("--host-saturation-min-observations", type=int, default=5)
    parser.add_argument("--host-saturation-low-value-threshold", type=float, default=0.15)
    parser.add_argument("--saturated-host-budget", type=int, default=1)
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
