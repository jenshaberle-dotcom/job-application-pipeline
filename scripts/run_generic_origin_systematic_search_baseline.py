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
    all_jobs: dict[str, dict] = {}

    for index, source in enumerate(sources, start=1):
        source_name = str(source["source_name"])
        origin_url = str(source["origin_url"])
        source_jobs: dict[str, dict] = {}
        outcomes: list[dict] = []
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

            serialized = _serialize_outcome(outcome)
            outcomes.append(serialized)
            if outcome.mechanism != "none":
                mechanisms.add(outcome.mechanism)
            for job in outcome.jobs:
                key = job.final_url
                source_jobs.setdefault(key, asdict(job))
                all_jobs.setdefault(f"{source_name}|{key}", asdict(job))

            print(
                "SEARCH_RESULT="
                f"{source_name}|term={term}|mechanism={outcome.mechanism}|"
                f"pages={outcome.pages_requested}|"
                f"candidates={outcome.detail_candidates_seen}|"
                f"jobs={len(outcome.jobs)}|unique_source_jobs={len(source_jobs)}|"
                f"exhausted={str(outcome.exhausted).lower()}|"
                f"stop={outcome.stop_reason}"
            )

        operational = bool(mechanisms) and source_error is None
        pagination_exercised = any(row["pages_requested"] > 1 for row in outcomes)
        source_rows.append(
            {
                **source,
                "search_operational": operational,
                "mechanisms": sorted(mechanisms),
                "pagination_exercised": pagination_exercised,
                "unique_job_count": len(source_jobs),
                "jobs": list(source_jobs.values()),
                "outcomes": outcomes,
                "error": source_error,
            }
        )

    operational_count = sum(1 for row in source_rows if row["search_operational"])
    delivering_count = sum(1 for row in source_rows if row["unique_job_count"] > 0)
    pagination_count = sum(1 for row in source_rows if row["pagination_exercised"])

    payload = {
        "status": "generic_origin_systematic_search_baseline",
        "transaction_read_only": transaction_read_only,
        "canonical_search_terms": terms,
        "summary": {
            "active_source_count": len(source_rows),
            "search_operational_source_count": operational_count,
            "delivering_source_count": delivering_count,
            "pagination_exercised_source_count": pagination_count,
            "unique_job_count": len(all_jobs),
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
    print(f"S_BASELINE_SEARCH_OPERATIONAL={operational_count}")
    print(f"S_BASELINE_DELIVERING_SOURCES={delivering_count}")
    print(f"S_BASELINE_PAGINATION_EXERCISED={pagination_count}")
    print(f"Y_BASELINE_UNIQUE_JOBS={len(all_jobs)}")
    print(f"S_BASELINE_HTTP_REQUESTS={executor.calls}")
    print("S_BASELINE_DATABASE_WRITES=0")
    print("S_BASELINE=COMPLETE")


if __name__ == "__main__":
    main()
