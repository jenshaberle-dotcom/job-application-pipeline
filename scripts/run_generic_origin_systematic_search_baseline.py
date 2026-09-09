from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
import requests

from src.config import get_database_config
from src.connectors.generic_employer_origin_search import (
    DEFAULT_JOB_CAP,
    DEFAULT_PAGE_CAP,
    DEFAULT_PAGE_SIZE,
    GenericSearchOutcome,
    SearchRequest,
    search_generic_origin,
)

REQUEST_TIMEOUT_SECONDS = 30.0
MAX_TOTAL_REQUESTS = 2_000
QUERY_CONTROL_TERM = "qzxvplmn847362951"
QUERY_CONTROL_JOB_CAP = 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only targeted-search baseline for active generic Employer-Origin "
            "sources. Uses the current canonical StepStone raster unchanged."
        )
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--page-cap", type=int, default=DEFAULT_PAGE_CAP)
    parser.add_argument("--job-cap", type=int, default=DEFAULT_JOB_CAP)
    parser.add_argument("--source-cap", type=int)
    parser.add_argument("--term-cap", type=int)
    parser.add_argument("--max-total-requests", type=int, default=MAX_TOTAL_REQUESTS)
    return parser


def _load_inputs() -> tuple[list[dict], list[str], str]:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW transaction_read_only")
            transaction_read_only = str(cur.fetchone()["transaction_read_only"])
            if transaction_read_only != "on":
                raise RuntimeError("systematic search baseline must be read-only")

            cur.execute(
                """
                SELECT source_name, company_key, origin_url, candidate_id
                FROM generic_employer_origin_active_sources
                ORDER BY source_name
                """
            )
            sources = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT st.search_term
                FROM search_terms AS st
                JOIN search_profiles AS sp ON sp.id = st.search_profile_id
                WHERE sp.profile_name = 'stepstone_data_engineer_hannover'
                  AND sp.is_active = TRUE
                  AND st.is_active = TRUE
                ORDER BY st.id
                """
            )
            terms = [str(row["search_term"]) for row in cur.fetchall()]

    if not sources:
        raise RuntimeError("no active generic Employer-Origin sources")
    if not terms:
        raise RuntimeError("canonical StepStone search raster is empty")
    return sources, terms, transaction_read_only


class MeteredHttpExecutor:
    def __init__(self, *, max_requests: int) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "job-application-pipeline-generic-search/1.0",
                "Accept": (
                    "text/html,application/xhtml+xml,application/json,"
                    "application/xml,*/*;q=0.8"
                ),
            }
        )
        self.max_requests = max_requests
        self.calls = 0

    def __call__(self, request: SearchRequest) -> tuple[str, str, int]:
        if self.calls >= self.max_requests:
            raise RuntimeError("systematic search absolute request cap exceeded")
        self.calls += 1
        method = request.method.upper()
        fields = dict(request.fields)
        if method == "GET":
            response = self.session.get(
                request.url,
                params=fields or None,
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=True,
            )
        elif method == "POST" and request.payload_kind == "json":
            response = self.session.post(
                request.url,
                json=fields,
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=False,
                headers={"Content-Type": "application/json"},
            )
        elif method == "POST" and request.payload_kind == "form":
            response = self.session.post(
                request.url,
                data=list(request.fields),
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=True,
            )
        else:
            raise RuntimeError(
                f"unsupported targeted search request: {method}/{request.payload_kind}"
            )
        body = response.content
        if len(body) > 5_000_000:
            raise RuntimeError("systematic search response body cap exceeded")
        return (
            body.decode(response.encoding or "utf-8", errors="replace"),
            str(response.url),
            int(response.status_code),
        )


def _serialize_outcome(outcome: GenericSearchOutcome) -> dict:
    return {
        "mechanism": outcome.mechanism,
        "query": outcome.query,
        "pages_requested": outcome.pages_requested,
        "detail_candidates_seen": outcome.detail_candidates_seen,
        "job_count": len(outcome.jobs),
        "exhausted": outcome.exhausted,
        "stop_reason": outcome.stop_reason,
        "final_url": outcome.final_url,
        "jobs": [asdict(job) for job in outcome.jobs],
    }


def _job_urls(outcome: GenericSearchOutcome) -> set[str]:
    return {job.final_url for job in outcome.jobs}


def _query_semantics_status(
    *,
    target_outcomes: list[GenericSearchOutcome],
    control_outcome: GenericSearchOutcome | None,
    source_error: str | None,
) -> tuple[str, str]:
    if source_error is not None:
        return "failed", "target_or_control_error"
    mechanisms = {
        outcome.mechanism for outcome in target_outcomes if outcome.mechanism != "none"
    }
    if not mechanisms:
        return "not_available", "no_deterministic_targeted_search_surface"
    if control_outcome is None or control_outcome.mechanism == "none":
        return "failed", "control_query_could_not_use_same_search_surface"
    if control_outcome.stop_reason in {
        "inventory_request_failed",
        "search_request_failed",
        "origin_unreachable",
    }:
        return "failed", "control_query_request_failed"

    positive_targets = [outcome for outcome in target_outcomes if outcome.jobs]
    control_urls = _job_urls(control_outcome)
    if control_urls:
        return "failed", "impossible_control_query_returned_jobs"
    if positive_targets:
        return "proven", "target_query_returned_jobs_control_query_returned_zero"
    return "unconfirmed_zero", "target_and_control_queries_returned_zero_jobs"


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.page_size < 1 or args.page_size > 50:
        raise SystemExit("--page-size must be between 1 and 50")
    if args.page_cap < 1 or args.page_cap > 5:
        raise SystemExit("--page-cap must be between 1 and 5")
    if args.job_cap < 1 or args.job_cap > 100:
        raise SystemExit("--job-cap must be between 1 and 100")
    if args.source_cap is not None and args.source_cap < 1:
        raise SystemExit("--source-cap must be >= 1")
    if args.term_cap is not None and args.term_cap < 1:
        raise SystemExit("--term-cap must be >= 1")
    if args.max_total_requests < 1:
        raise SystemExit("--max-total-requests must be >= 1")

    sources, terms, transaction_read_only = _load_inputs()
    if args.source_cap:
        sources = sources[: args.source_cap]
    if args.term_cap:
        terms = terms[: args.term_cap]

    executor = MeteredHttpExecutor(max_requests=args.max_total_requests)
    source_rows: list[dict] = []
    proven_jobs: dict[str, dict] = {}
    raw_target_jobs: dict[str, dict] = {}

    for index, source in enumerate(sources, start=1):
        source_name = str(source["source_name"])
        origin_url = str(source["origin_url"])
        source_jobs: dict[str, dict] = {}
        outcomes: list[dict] = []
        raw_outcomes: list[GenericSearchOutcome] = []
        mechanisms: set[str] = set()
        source_error: str | None = None

        print(f"SOURCE={index}/{len(sources)}|{source_name}|origin={origin_url}")

        for term in terms:
            if len(source_jobs) >= args.job_cap:
                break
            try:
                outcome = search_generic_origin(
                    origin_url=origin_url,
                    query=term,
                    execute=executor,
                    page_size=args.page_size,
                    page_cap=args.page_cap,
                    job_cap=max(1, args.job_cap - len(source_jobs)),
                )
            except Exception as exc:
                source_error = f"{type(exc).__name__}:{exc}"
                print(f"SEARCH_ERROR={source_name}|term={term}|{source_error}")
                break

            raw_outcomes.append(outcome)
            serialized = _serialize_outcome(outcome)
            outcomes.append(serialized)
            if outcome.mechanism != "none":
                mechanisms.add(outcome.mechanism)
            for job in outcome.jobs:
                key = job.final_url
                source_jobs.setdefault(key, asdict(job))
                raw_target_jobs.setdefault(f"{source_name}|{key}", asdict(job))

            print(
                "SEARCH_RESULT="
                f"{source_name}|term={term}|mechanism={outcome.mechanism}|"
                f"pages={outcome.pages_requested}|"
                f"candidates={outcome.detail_candidates_seen}|"
                f"jobs={len(outcome.jobs)}|unique_source_jobs={len(source_jobs)}|"
                f"exhausted={str(outcome.exhausted).lower()}|"
                f"stop={outcome.stop_reason}"
            )

        control_outcome: GenericSearchOutcome | None = None
        if mechanisms and source_error is None:
            try:
                control_outcome = search_generic_origin(
                    origin_url=origin_url,
                    query=QUERY_CONTROL_TERM,
                    execute=executor,
                    page_size=args.page_size,
                    page_cap=args.page_cap,
                    job_cap=min(QUERY_CONTROL_JOB_CAP, args.job_cap),
                )
            except Exception as exc:
                source_error = f"{type(exc).__name__}:{exc}"
                print(
                    f"SEARCH_CONTROL_ERROR={source_name}|term={QUERY_CONTROL_TERM}|"
                    f"{source_error}"
                )

        semantics_status, semantics_reason = _query_semantics_status(
            target_outcomes=raw_outcomes,
            control_outcome=control_outcome,
            source_error=source_error,
        )
        if control_outcome is not None:
            print(
                "SEARCH_CONTROL="
                f"{source_name}|mechanism={control_outcome.mechanism}|"
                f"jobs={len(control_outcome.jobs)}|"
                f"candidates={control_outcome.detail_candidates_seen}|"
                f"stop={control_outcome.stop_reason}"
            )
        print(
            f"SEARCH_SEMANTICS={source_name}|status={semantics_status}|"
            f"reason={semantics_reason}"
        )

        search_surface_detected = bool(mechanisms) and source_error is None
        search_semantics_proven = semantics_status == "proven"
        pagination_exercised = any(row["pages_requested"] > 1 for row in outcomes)
        if search_semantics_proven:
            for key, job in source_jobs.items():
                proven_jobs.setdefault(f"{source_name}|{key}", job)

        source_rows.append(
            {
                **source,
                "search_surface_detected": search_surface_detected,
                "search_semantics_status": semantics_status,
                "search_semantics_reason": semantics_reason,
                "search_semantics_proven": search_semantics_proven,
                "mechanisms": sorted(mechanisms),
                "pagination_exercised": pagination_exercised,
                "target_unique_job_count": len(source_jobs),
                "accepted_y_job_count": len(source_jobs) if search_semantics_proven else 0,
                "jobs": list(source_jobs.values()),
                "outcomes": outcomes,
                "control_outcome": (
                    _serialize_outcome(control_outcome)
                    if control_outcome is not None
                    else None
                ),
                "error": source_error,
            }
        )

    surface_count = sum(1 for row in source_rows if row["search_surface_detected"])
    semantics_proven_count = sum(
        1 for row in source_rows if row["search_semantics_proven"]
    )
    delivering_candidate_count = sum(
        1 for row in source_rows if row["target_unique_job_count"] > 0
    )
    delivering_proven_count = sum(
        1 for row in source_rows if row["accepted_y_job_count"] > 0
    )
    pagination_count = sum(1 for row in source_rows if row["pagination_exercised"])
    unconfirmed_zero_count = sum(
        1 for row in source_rows if row["search_semantics_status"] == "unconfirmed_zero"
    )
    semantics_failed_count = sum(
        1 for row in source_rows if row["search_semantics_status"] == "failed"
    )

    payload = {
        "status": "generic_origin_systematic_search_baseline",
        "transaction_read_only": transaction_read_only,
        "canonical_search_terms": terms,
        "query_control_term": QUERY_CONTROL_TERM,
        "summary": {
            "active_source_count": len(source_rows),
            "search_surface_detected_source_count": surface_count,
            "search_semantics_proven_source_count": semantics_proven_count,
            "search_semantics_unconfirmed_zero_source_count": unconfirmed_zero_count,
            "search_semantics_failed_source_count": semantics_failed_count,
            "raw_delivering_source_count": delivering_candidate_count,
            "accepted_y_delivering_source_count": delivering_proven_count,
            "pagination_exercised_source_count": pagination_count,
            "raw_target_job_count": len(raw_target_jobs),
            "accepted_y_job_count": len(proven_jobs),
            "http_request_count": executor.calls,
        },
        "sources": source_rows,
        "boundary": {
            "database_writes": False,
            "bronze_writes": False,
            "silver_writes": False,
            "network_requests": True,
            "targeted_native_search_only": True,
            "full_scrape": False,
            "vocabulary_tuning": False,
            "search_space_expansion": False,
            "query_discrimination_required_for_s": True,
            "page_cap": args.page_cap,
            "job_cap_per_source": args.job_cap,
            "absolute_request_cap": args.max_total_requests,
        },
    }

    output = Path(args.output)
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print(f"S_BASELINE_ACTIVE_SOURCES={len(source_rows)}")
    print(f"S_BASELINE_SEARCH_SURFACE_DETECTED={surface_count}")
    print(f"S_BASELINE_QUERY_SEMANTICS_PROVEN={semantics_proven_count}")
    print(f"S_BASELINE_QUERY_SEMANTICS_UNCONFIRMED_ZERO={unconfirmed_zero_count}")
    print(f"S_BASELINE_QUERY_SEMANTICS_FAILED={semantics_failed_count}")
    print(f"S_BASELINE_RAW_DELIVERING_SOURCES={delivering_candidate_count}")
    print(f"S_BASELINE_ACCEPTED_Y_DELIVERING_SOURCES={delivering_proven_count}")
    print(f"S_BASELINE_PAGINATION_EXERCISED={pagination_count}")
    print(f"Y_BASELINE_RAW_TARGET_JOBS={len(raw_target_jobs)}")
    print(f"Y_BASELINE_ACCEPTED_JOBS={len(proven_jobs)}")
    print(f"S_BASELINE_HTTP_REQUESTS={executor.calls}")
    print("S_BASELINE_DATABASE_WRITES=0")
    print("S_BASELINE=COMPLETE")


if __name__ == "__main__":
    main()
