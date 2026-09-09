from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from typing import Callable
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row
import requests

from src.config import get_database_config
from src.connectors.base import JobSourceConnector, RawJobRecord, SearchProfile, SearchTerm
from src.connectors.capabilities import SourceCapabilities
from src.connectors.employer_origin_acquisition import (
    AcquiredJobPage,
    explicit_root_delegated_listing_hosts,
    parse_page,
)
from src.connectors.employer_origin_acquisition_v4 import acquire_genuine_job_pages
from src.connectors.employer_origin_acquisition_v4_forms import MeteredRequest
from src.connectors.employer_origin_ats_navigation import authorized_ats_provider
from src.connectors.employer_origin_portal_delegation_acquisition import acquire_via_explicit_portal
from src.connectors.employer_origin_provider_public_feed import (
    SUPPORTED_PUBLIC_FEED_PROVIDERS,
    acquire_from_authorized_provider_host,
)
from src.connectors.employer_origin_workday_acquisition import (
    WorkdayAcquisitionRequest,
    acquire_workday_job_page,
)
from src.search_intelligence.ats_provider_registry import recognize_ats_provider

REQUEST_TIMEOUT_SECONDS = 30.0
MAX_BODY_BYTES = 5_000_000
WORKDAY_REQUEST_CAP = 3
PORTAL_REQUEST_CAP = 4
PUBLIC_FEED_REQUEST_CAP = 3
ACTIVE_SOURCE_RELATION = "generic_employer_origin_active_sources"


@dataclass(frozen=True)
class GenericOriginSource:
    candidate_id: int
    company_key: str
    company_name: str
    candidate_url: str


CandidateLoader = Callable[[str], GenericOriginSource]


def _active_projection_exists(conn: psycopg.Connection[object]) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT to_regclass(%s) IS NOT NULL AS relation_exists",
            (f"public.{ACTIVE_SOURCE_RELATION}",),
        )
        row = cur.fetchone()
    return bool(row and row["relation_exists"])


def load_generic_origin_source(company_key: str) -> GenericOriginSource:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        row = None
        if _active_projection_exists(conn):
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        active.candidate_id AS id,
                        active.company_key,
                        candidate.company_name,
                        active.origin_url AS candidate_url
                    FROM {ACTIVE_SOURCE_RELATION} AS active
                    JOIN employer_origin_source_candidates AS candidate
                      ON candidate.id = active.candidate_id
                    WHERE active.company_key = %s
                    LIMIT 1
                    """,
                    (company_key,),
                )
                row = cur.fetchone()

        if row is None:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, company_key, company_name, candidate_url
                    FROM employer_origin_source_candidates
                    WHERE company_key = %s
                    ORDER BY updated_at DESC NULLS LAST, id DESC
                    LIMIT 1
                    """,
                    (company_key,),
                )
                row = cur.fetchone()

    if row is None:
        raise ValueError(f"No Employer-Origin candidate found for {company_key!r}")
    candidate_url = str(row.get("candidate_url") or "").strip()
    if not candidate_url:
        raise ValueError(
            f"Employer-Origin candidate {company_key!r} has no materialized origin URL"
        )
    return GenericOriginSource(
        candidate_id=int(row["id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        candidate_url=candidate_url,
    )


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "job-application-pipeline-generic-origin/1.0",
            "Accept": "text/html,application/xhtml+xml,application/json,application/xml,*/*;q=0.8",
        }
    )
    return session


def _read_response(response: requests.Response) -> tuple[str, str, int]:
    body = response.content
    if len(body) > MAX_BODY_BYTES:
        raise RuntimeError("generic Employer-Origin response body cap exceeded")
    return (
        body.decode(response.encoding or "utf-8", errors="replace"),
        str(response.url),
        int(response.status_code),
    )


def _direct_job(source: GenericOriginSource) -> AcquiredJobPage | None:
    host = (urlparse(source.candidate_url).hostname or "").casefold()
    if not host:
        return None
    session = _session()

    def fetcher(url: str) -> tuple[str, str, int]:
        return _read_response(
            session.get(url, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
        )

    try:
        jobs, _ = acquire_genuine_job_pages(
            listing_url=source.candidate_url,
            allowed_hosts=(host,),
            known_detail_urls=(),
            fetcher=fetcher,
            max_followup_requests=3,
            max_results=1,
        )
    except Exception:
        return None
    return jobs[0] if jobs else None


def _workday_job(source: GenericOriginSource) -> AcquiredJobPage | None:
    host = (urlparse(source.candidate_url).hostname or "").casefold()
    if not host:
        return None
    session = _session()
    calls = 0

    def execute(request: WorkdayAcquisitionRequest) -> tuple[str, str, int]:
        nonlocal calls
        if calls >= WORKDAY_REQUEST_CAP:
            raise RuntimeError("generic Workday request cap exceeded")
        calls += 1
        method = request.method.upper()
        if method == "GET":
            response = session.get(
                request.url,
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=True,
            )
        elif method == "POST":
            response = session.post(
                request.url,
                json=dict(request.json_fields),
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=False,
                headers={"Content-Type": "application/json"},
            )
        else:
            raise RuntimeError(f"unsupported Workday method: {method}")
        return _read_response(response)

    try:
        job, _ = acquire_workday_job_page(
            listing_url=source.candidate_url,
            allowed_hosts=(host,),
            request_executor=execute,
        )
    except Exception:
        return None
    return job


def _portal_job(source: GenericOriginSource) -> AcquiredJobPage | None:
    host = (urlparse(source.candidate_url).hostname or "").casefold()
    if not host:
        return None
    session = _session()
    calls = 0

    def execute(request: MeteredRequest) -> tuple[str, str, int]:
        nonlocal calls
        if calls >= PORTAL_REQUEST_CAP:
            raise RuntimeError("generic portal request cap exceeded")
        calls += 1
        method = request.method.upper()
        fields = dict(request.fields)
        if method == "GET":
            response = session.get(
                request.url,
                params=fields or None,
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=True,
            )
        elif method == "POST":
            response = session.post(
                request.url,
                data=fields,
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=True,
            )
        else:
            raise RuntimeError(f"unsupported portal method: {method}")
        return _read_response(response)

    try:
        jobs, _ = acquire_via_explicit_portal(
            listing_url=source.candidate_url,
            allowed_hosts=(host,),
            known_detail_urls=(),
            fetcher=lambda url: execute(MeteredRequest(url)),
            request_executor=execute,
            max_followup_requests=2,
            max_results=1,
        )
    except Exception:
        return None
    return jobs[0] if jobs else None


def _public_feed_job(source: GenericOriginSource) -> AcquiredJobPage | None:
    host = (urlparse(source.candidate_url).hostname or "").casefold()
    if not host:
        return None
    session = _session()
    try:
        root_html, root_final, root_status = _read_response(
            session.get(
                source.candidate_url,
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=True,
            )
        )
    except Exception:
        return None
    if root_status >= 400:
        return None
    root_host = (urlparse(root_final).hostname or "").casefold()
    allowed_hosts = {value for value in (host, root_host) if value}
    root = parse_page(
        requested_url=source.candidate_url,
        html=root_html,
        final_url=root_final,
        status_code=root_status,
    )
    delegated_hosts = set(
        explicit_root_delegated_listing_hosts(root, allowed_hosts=allowed_hosts)
    )
    provider = authorized_ats_provider(
        page_url=root.final_url,
        html=root.html,
        allowed_hosts=allowed_hosts,
        delegated_hosts=delegated_hosts,
    )
    provider_page = root.final_url
    if provider is None:
        matches: list[tuple[str, str]] = []
        for delegated_host in delegated_hosts:
            recognition = recognize_ats_provider(f"https://{delegated_host}/")
            if recognition is not None:
                matches.append((recognition.provider, delegated_host))
        matches = list(dict.fromkeys(matches))
        if len(matches) != 1:
            return None
        provider, delegated_host = matches[0]
        provider_page = f"https://{delegated_host}/"
    if provider not in SUPPORTED_PUBLIC_FEED_PROVIDERS:
        return None
    provider_host = (urlparse(provider_page).hostname or "").casefold()
    if not provider_host:
        return None
    calls = 0

    def fetcher(url: str) -> tuple[str, str, int]:
        nonlocal calls
        if calls >= PUBLIC_FEED_REQUEST_CAP:
            raise RuntimeError("generic public-feed request cap exceeded")
        parsed = urlparse(url)
        if parsed.scheme.casefold() != "https" or (parsed.hostname or "").casefold() != provider_host:
            raise RuntimeError("public-feed request left authorized provider host")
        calls += 1
        return _read_response(
            session.get(url, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
        )

    try:
        result = acquire_from_authorized_provider_host(
            provider=provider,
            provider_page_url=provider_page,
            allowed_hosts=(provider_host,),
            fetcher=fetcher,
            max_detail_attempts=2,
        )
    except Exception:
        return None
    return result.acquired_job if result is not None else None


def acquire_one_generic_job(source: GenericOriginSource) -> AcquiredJobPage | None:
    for acquire in (_direct_job, _workday_job, _portal_job, _public_feed_job):
        job = acquire(source)
        if job is not None:
            return job
    return None


def _stable_external_job_id(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1] or "job"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return f"{slug}:{digest}"


def _record(source_name: str, source: GenericOriginSource, job: AcquiredJobPage, search_term: str) -> RawJobRecord:
    title = str(job.title or job.anchor_text or "Job").strip() or "Job"
    observed_at = datetime.now(UTC).isoformat()
    return RawJobRecord(
        source_name=source_name,
        source_url=job.final_url,
        external_job_id=_stable_external_job_id(job.final_url),
        raw_data={
            "source_type": "employer_origin_career_site",
            "source_family": "generic_origin",
            "source_target": source.company_key,
            "result_card": {
                "title": title,
                "company_name": source.company_name,
                "detail_url": job.final_url,
            },
            "job": {
                "title": title,
                "company_name": source.company_name,
                "source_url": job.final_url,
            },
            "acquisition_evidence": {
                "proof_kind": job.proof_kind,
                "discovery_source": job.discovery_source,
                "candidate_id": source.candidate_id,
                "generic_layer_product": True,
                "search_term_requested": search_term,
            },
            "observed_at_utc": observed_at,
        },
    )


class GenericEmployerOriginConnector(JobSourceConnector):
    capabilities = SourceCapabilities(
        supports_keyword=False,
        supports_location=False,
        supports_radius=False,
        supports_employment_type=False,
        supports_remote_filter=False,
        supports_pagination=False,
        supports_full_fetch=False,
    )

    def __init__(
        self,
        *,
        company_key: str,
        source_name: str | None = None,
        candidate_loader: CandidateLoader = load_generic_origin_source,
    ) -> None:
        self.company_key = company_key
        self.source_name = source_name or f"generic_origin:{company_key}"
        self.candidate_loader = candidate_loader

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        del profile
        source = self.candidate_loader(self.company_key)
        job = acquire_one_generic_job(source)
        if job is None:
            return [], source.candidate_url
        return [
            _record(
                self.source_name,
                source,
                job,
                search_term.search_term,
            )
        ], source.candidate_url
