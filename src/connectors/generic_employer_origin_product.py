from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import psycopg
import requests

from src.config import get_database_config
from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.employer_origin_acquisition import AcquiredJobPage, canonical_url
from src.connectors.generic_employer_origin import (
    GenericEmployerOriginConnector,
    GenericOriginSource,
    _record,
)
from src.connectors.generic_employer_origin_search import (
    DEFAULT_JOB_CAP,
    DEFAULT_PAGE_CAP,
    DEFAULT_PAGE_SIZE,
    GenericSearchOutcome,
    SearchRequest,
    search_generic_origin,
)
from src.connectors.generic_job_detail_evidence import (
    extract_generic_job_detail_evidence,
    project_detail_evidence_into_raw_data,
)
from src.ingestion.generic_origin_bronze_admission import (
    filter_generic_origin_bronze_records,
)


LOGGER = logging.getLogger(__name__)

NEUTRAL_TRIGGER_TERM = "*"
CANONICAL_TARGET_PROFILE_NAME = "stepstone_data_engineer_hannover"
QUERY_CONTROL_TERM = "qzxvplmn847362951"
QUERY_CONTROL_JOB_CAP = 5
PRODUCT_MAX_REQUESTS = 250
MAX_BODY_BYTES = 5_000_000
MAX_TARGET_TERMS = 12


@dataclass(frozen=True)
class QueryProvenJob:
    job: AcquiredJobPage
    query: str
    mechanism: str
    detail_evidence: dict[str, Any]


@dataclass(frozen=True)
class QueryProvenSearchResult:
    status: str
    reason: str
    jobs: tuple[QueryProvenJob, ...]
    request_count: int


class ProductSearchExecutor:
    """Bounded HTTP executor for the production generic targeted-search path."""

    def __init__(self, *, max_requests: int = PRODUCT_MAX_REQUESTS) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "job-application-pipeline-generic-product-search/1.0",
                "Accept": (
                    "text/html,application/xhtml+xml,application/json,"
                    "application/xml,*/*;q=0.8"
                ),
            }
        )
        self.max_requests = max_requests
        self.calls = 0
        self._plain_get_responses: dict[str, tuple[str, str, int]] = {}

    def cached_plain_get(self, url: str) -> tuple[str, str, int] | None:
        return self._plain_get_responses.get(canonical_url(url))

    def __call__(self, request: SearchRequest) -> tuple[str, str, int]:
        if self.calls >= self.max_requests:
            raise RuntimeError("generic product search absolute request cap exceeded")
        self.calls += 1

        method = request.method.upper()
        fields = dict(request.fields)
        if method == "GET":
            response = self.session.get(
                request.url,
                params=fields or None,
                timeout=30.0,
                allow_redirects=True,
            )
        elif method == "POST" and request.payload_kind == "json":
            response = self.session.post(
                request.url,
                json=fields,
                timeout=30.0,
                allow_redirects=False,
                headers={"Content-Type": "application/json"},
            )
        elif method == "POST" and request.payload_kind == "form":
            response = self.session.post(
                request.url,
                data=list(request.fields),
                timeout=30.0,
                allow_redirects=True,
            )
        else:
            raise RuntimeError(
                f"unsupported generic product search request: {method}/{request.payload_kind}"
            )

        body = response.content
        if len(body) > MAX_BODY_BYTES:
            raise RuntimeError("generic product search response body cap exceeded")
        result = (
            body.decode(response.encoding or "utf-8", errors="replace"),
            str(response.url),
            int(response.status_code),
        )
        if method == "GET" and not fields:
            self._plain_get_responses[canonical_url(request.url)] = result
            self._plain_get_responses[canonical_url(result[1])] = result
        return result


def load_canonical_target_terms() -> list[str]:
    """Load the existing canonical target raster without changing source activation."""

    with psycopg.connect(**get_database_config()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT st.search_term
                FROM search_terms AS st
                JOIN search_profiles AS sp ON sp.id = st.search_profile_id
                WHERE sp.profile_name = %s
                  AND sp.is_active = TRUE
                  AND st.is_active = TRUE
                ORDER BY st.id
                """,
                (CANONICAL_TARGET_PROFILE_NAME,),
            )
            terms = [str(row[0]).strip() for row in cur.fetchall()]

    terms = list(dict.fromkeys(term for term in terms if term and term != NEUTRAL_TRIGGER_TERM))
    if not terms:
        raise RuntimeError("canonical target search raster is empty")
    return terms


def load_company_target_terms(company_key: str) -> list[str]:
    """Prefer proof-grounded company vocabulary, then fill from the canonical raster.

    `origin_job_title` observations are produced only from the materialized proof=PASS
    origin cohort. Market vocabulary remains a lower-authority prior. Neither source
    mutates search profiles; this function is the bounded execution projection.
    """

    learned: list[str] = []
    try:
        with psycopg.connect(**get_database_config()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT to_regclass('public.company_vocabulary_observations') IS NOT NULL"
                )
                row = cur.fetchone()
                if row and bool(row[0]):
                    cur.execute(
                        """
                        SELECT observed_term
                        FROM company_vocabulary_observations
                        WHERE company_key = %s
                          AND evidence_type IN ('origin_job_title', 'market_evidence_title')
                          AND btrim(observed_term) <> ''
                        ORDER BY
                            CASE evidence_type
                                WHEN 'origin_job_title' THEN 0
                                ELSE 1
                            END,
                            observation_count DESC,
                            last_seen_at DESC,
                            observed_term
                        LIMIT %s
                        """,
                        (company_key, MAX_TARGET_TERMS),
                    )
                    learned = [str(item[0]).strip() for item in cur.fetchall()]
    except psycopg.Error as exc:
        LOGGER.warning(
            "Company vocabulary unavailable; canonical fallback retained: company=%s error=%s",
            company_key,
            exc,
        )

    canonical = load_canonical_target_terms()
    combined = list(
        dict.fromkeys(
            term
            for term in (*learned, *canonical)
            if term and term != NEUTRAL_TRIGGER_TERM
        )
    )
    if not combined:
        raise RuntimeError("company and canonical target vocabulary are empty")
    return combined[:MAX_TARGET_TERMS]


def _job_urls(outcome: GenericSearchOutcome) -> set[str]:
    return {job.final_url for job in outcome.jobs}


def query_semantics_status(
    *,
    target_outcomes: list[GenericSearchOutcome],
    control_outcome: GenericSearchOutcome | None,
    source_error: str | None = None,
) -> tuple[str, str]:
    """Use the same fail-closed query-discrimination contract as the live audit."""

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


def _detail_evidence(
    *,
    job: AcquiredJobPage,
    executor: ProductSearchExecutor,
    cache: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    key = canonical_url(job.final_url)
    if key in cache:
        return cache[key]

    response = executor.cached_plain_get(job.final_url)
    if response is None:
        response = executor(SearchRequest(job.final_url))
    body, final_url, status_code = response
    if not (200 <= int(status_code) < 400) or canonical_url(final_url) != key:
        return None

    evidence = extract_generic_job_detail_evidence(
        html=body,
        url=final_url,
        page_title=job.title,
    )
    evidence = dict(evidence)
    # Migration 099 consumes this exact HTTP evidence together with the exact-bound
    # recurring observation to establish employer-origin exact-detail lifecycle truth.
    evidence["status_code"] = int(status_code)
    cache[key] = evidence
    return evidence


def acquire_query_proven_jobs(
    *,
    source: GenericOriginSource,
    target_terms: list[str],
    executor: ProductSearchExecutor | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    page_cap: int = DEFAULT_PAGE_CAP,
    job_cap: int = DEFAULT_JOB_CAP,
) -> QueryProvenSearchResult:
    """Search one active source and return jobs only after query semantics are proven."""

    if not target_terms:
        raise ValueError("target_terms must not be empty")
    if job_cap < 1:
        raise ValueError("job_cap must be positive")

    http = executor or ProductSearchExecutor()
    target_outcomes: list[GenericSearchOutcome] = []
    jobs_by_url: dict[str, tuple[AcquiredJobPage, str, str]] = {}

    try:
        for term in target_terms:
            remaining = max(1, job_cap - len(jobs_by_url))
            outcome = search_generic_origin(
                origin_url=source.candidate_url,
                query=term,
                execute=http,
                page_size=page_size,
                page_cap=page_cap,
                job_cap=remaining,
            )
            target_outcomes.append(outcome)
            for job in outcome.jobs:
                jobs_by_url.setdefault(job.final_url, (job, term, outcome.mechanism))
            if len(jobs_by_url) >= job_cap:
                break

        control_outcome = search_generic_origin(
            origin_url=source.candidate_url,
            query=QUERY_CONTROL_TERM,
            execute=http,
            page_size=page_size,
            page_cap=page_cap,
            job_cap=QUERY_CONTROL_JOB_CAP,
        )
    except Exception as exc:
        return QueryProvenSearchResult(
            status="failed",
            reason=f"target_or_control_error:{type(exc).__name__}:{exc}",
            jobs=(),
            request_count=http.calls,
        )

    status, reason = query_semantics_status(
        target_outcomes=target_outcomes,
        control_outcome=control_outcome,
    )
    if status != "proven":
        return QueryProvenSearchResult(status, reason, (), http.calls)

    evidence_cache: dict[str, dict[str, Any]] = {}
    proven_jobs: list[QueryProvenJob] = []
    try:
        for job, term, mechanism in jobs_by_url.values():
            evidence = _detail_evidence(
                job=job,
                executor=http,
                cache=evidence_cache,
            )
            if evidence is None:
                continue
            proven_jobs.append(
                QueryProvenJob(
                    job=job,
                    query=term,
                    mechanism=mechanism,
                    detail_evidence=evidence,
                )
            )
    except Exception as exc:
        return QueryProvenSearchResult(
            status="failed",
            reason=f"detail_evidence_error:{type(exc).__name__}:{exc}",
            jobs=(),
            request_count=http.calls,
        )

    return QueryProvenSearchResult(
        status="proven",
        reason=reason,
        jobs=tuple(proven_jobs),
        request_count=http.calls,
    )


def _product_record(
    *,
    source_name: str,
    source: GenericOriginSource,
    item: QueryProvenJob,
) -> RawJobRecord:
    base = _record(source_name, source, item.job, item.query)
    raw_data = project_detail_evidence_into_raw_data(
        base.raw_data,
        item.detail_evidence,
    )

    boundary = raw_data.get("acquisition_boundary")
    if not isinstance(boundary, dict):
        boundary = {}
    boundary.update(
        {
            "detail_pages_fetched": True,
            "query_semantics_proven": True,
            "query_control_term": QUERY_CONTROL_TERM,
            "target_profile_name": CANONICAL_TARGET_PROFILE_NAME,
            "company_vocabulary_key": source.company_key,
        }
    )
    raw_data["acquisition_boundary"] = boundary

    acquisition = raw_data.get("acquisition_evidence")
    if not isinstance(acquisition, dict):
        acquisition = {}
    acquisition.update(
        {
            "query_semantics_status": "proven",
            "search_mechanism": item.mechanism,
            "neutral_execution_trigger": NEUTRAL_TRIGGER_TERM,
            "target_vocabulary_scope": "company_vocabulary_then_canonical_fallback",
        }
    )
    raw_data["acquisition_evidence"] = acquisition

    return RawJobRecord(
        source_name=base.source_name,
        source_url=base.source_url,
        external_job_id=base.external_job_id,
        raw_data=raw_data,
    )


class GenericEmployerOriginProductConnector(GenericEmployerOriginConnector):
    """Production Employer-Origin connector with query proof and Bronze job gating.

    The generic layer ``proof=PASS`` gate decides whether the source itself is
    valid and active. The recurring profile keeps ``*`` as a non-semantic execution
    trigger. Product acquisition prefers company vocabulary learned from the proved
    origin, fills only missing breadth from the canonical target raster, proves
    target-vs-impossible-control query discrimination, enriches exact detail pages
    locally, and only then exposes records to the existing Bronze gate. A valid
    source may therefore return zero records without losing source validity.
    """

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        if search_term.search_term != NEUTRAL_TRIGGER_TERM:
            records, final_url = super().fetch_jobs(profile, search_term)
            return filter_generic_origin_bronze_records(records), final_url

        source = self.candidate_loader(self.company_key)
        target_terms = load_company_target_terms(source.company_key)
        result = acquire_query_proven_jobs(
            source=source,
            target_terms=target_terms,
        )
        if result.status != "proven":
            LOGGER.warning(
                "Generic product search not admitted: source=%s status=%s reason=%s requests=%s",
                self.source_name,
                result.status,
                result.reason,
                result.request_count,
            )
            return [], source.candidate_url

        records = [
            _product_record(source_name=self.source_name, source=source, item=item)
            for item in result.jobs
        ]
        admitted = filter_generic_origin_bronze_records(records)
        LOGGER.info(
            "Generic product search admitted source=%s query_proven=%s bronze=%s requests=%s vocabulary_terms=%s",
            self.source_name,
            len(records),
            len(admitted),
            result.request_count,
            len(target_terms),
        )
        return admitted, source.candidate_url
