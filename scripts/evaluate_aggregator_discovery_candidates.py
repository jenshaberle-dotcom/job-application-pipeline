"""Evaluate aggregator/discovery-source candidates defensively.

This script is intentionally not a connector. It produces review artifacts for S2 source
strategy decisions and does not write to the database.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

import requests

DEFAULT_SEARCH_TERMS = (
    "Data Engineer",
    "Analytics Engineer",
    "ETL",
    "Data Platform",
    "Data Warehouse",
    "Big Data",
    "Python SQL",
)

DEFAULT_LOCATION = "Hannover"
DEFAULT_COUNTRY_CODE = "de"
DEFAULT_TIMEOUT_SECONDS = 20
REQUEST_SLEEP_SECONDS = 0.75
USER_AGENT = "job-application-pipeline/aggregator-discovery-evaluation"


@dataclass(frozen=True)
class AggregatorCandidate:
    platform: str
    source_role: str
    hard_gate_status: str
    access_path: str
    legal_terms_boundary: str
    automation_boundary: str
    requires_credentials: bool
    credential_env_vars: tuple[str, ...]
    probe_strategy: str
    recommendation_when_not_probed: str


@dataclass(frozen=True)
class JobMatch:
    platform: str
    query: str
    title: str
    company: str
    location: str
    remote_signal: str
    url: str
    source_job_id: str
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class CandidateEvaluation:
    platform: str
    source_role: str
    hard_gate_status: str
    access_path: str
    legal_terms_boundary: str
    automation_boundary: str
    requires_credentials: bool
    credential_env_vars: str
    probe_strategy: str
    probe_status: str
    probe_method: str
    request_count: int
    total_returned: int
    matching_jobs: int
    matching_companies: int
    matched_terms: str
    location_signal_counts: str
    recommendation: str
    notes: str


CANDIDATES: tuple[AggregatorCandidate, ...] = (
    AggregatorCandidate(
        platform="linkedin",
        source_role="research_only_discovery_signal",
        hard_gate_status="blocked_for_automation_without_approved_api_path",
        access_path="official/restricted API paths only; no scraping path accepted",
        legal_terms_boundary=(
            "Do not access, store or transfer LinkedIn content via scraping, crawling, "
            "spidering or other non-API acquisition."
        ),
        automation_boundary="no login automation, no browser automation, no connector",
        requires_credentials=True,
        credential_env_vars=("LINKEDIN_APPROVED_API_ACCESS",),
        probe_strategy="none_hard_gated",
        recommendation_when_not_probed="research-only; use only for one-off employer/vocabulary discovery",
    ),
    AggregatorCandidate(
        platform="xing",
        source_role="research_only_discovery_signal",
        hard_gate_status="blocked_for_search_ingestion_without_suitable_api_path",
        access_path="official E-Recruiting APIs appear posting/vendor oriented for this project",
        legal_terms_boundary="Treat as research-only unless a suitable approved search/discovery API is proven.",
        automation_boundary="no broad search scraping, no login automation, no connector",
        requires_credentials=True,
        credential_env_vars=("XING_APPROVED_API_ACCESS",),
        probe_strategy="none_hard_gated",
        recommendation_when_not_probed="research-only; useful for DACH employer and German role-title discovery",
    ),
    AggregatorCandidate(
        platform="indeed",
        source_role="research_only_discovery_signal",
        hard_gate_status="blocked_for_independent_broad_ingestion_without_partner_approval",
        access_path="partner/API access is approval controlled",
        legal_terms_boundary="Do not replicate Indeed search or build an independent aggregator-derived database.",
        automation_boundary="no scraping, no proxy workflow, no broad connector",
        requires_credentials=True,
        credential_env_vars=("INDEED_APPROVED_API_ACCESS",),
        probe_strategy="none_hard_gated",
        recommendation_when_not_probed="research-only/reference-only unless approved API use is available",
    ),
    AggregatorCandidate(
        platform="glassdoor",
        source_role="reference_only",
        hard_gate_status="blocked_for_automation_without_written_permission",
        access_path="no accepted job-search API path for this project",
        legal_terms_boundary="No automated agents, scraping, stripping or data mining without express permission.",
        automation_boundary="no harvesting, no review/salary scraping, no connector",
        requires_credentials=True,
        credential_env_vars=("GLASSDOOR_WRITTEN_PERMISSION",),
        probe_strategy="none_hard_gated",
        recommendation_when_not_probed="reference-only for occasional employer context, not job evidence",
    ),
    AggregatorCandidate(
        platform="stepstone",
        source_role="existing_defensive_source",
        hard_gate_status="already_bounded_in_project",
        access_path="existing one complete result-page boundary in current connector",
        legal_terms_boundary="Do not broaden without separate risk review.",
        automation_boundary="keep current defensive one-page boundary",
        requires_credentials=False,
        credential_env_vars=(),
        probe_strategy="none_existing_source",
        recommendation_when_not_probed="keep bounded; use existing source-value evaluation instead of new aggregator probing",
    ),
    AggregatorCandidate(
        platform="arbeitnow",
        source_role="bounded_discovery_probe_candidate",
        hard_gate_status="probe_allowed_with_public_api_boundary",
        access_path="public job-board API surface",
        legal_terms_boundary="Export only minimal discovery evidence; do not persist descriptions as raw job content.",
        automation_boundary="bounded API request, no detail pages, no DB writes",
        requires_credentials=False,
        credential_env_vars=(),
        probe_strategy="arbeitnow_public_api",
        recommendation_when_not_probed="run bounded API probe when source strategy needs Germany/remote discovery evidence",
    ),
    AggregatorCandidate(
        platform="adzuna",
        source_role="bounded_discovery_probe_candidate",
        hard_gate_status="probe_allowed_only_with_api_credentials_and_terms_review",
        access_path="official API with app_id/app_key",
        legal_terms_boundary="Use only within API terms and minimal evidence boundary.",
        automation_boundary="bounded API request, no detail pages, no DB writes",
        requires_credentials=True,
        credential_env_vars=("ADZUNA_APP_ID", "ADZUNA_APP_KEY"),
        probe_strategy="adzuna_search_api",
        recommendation_when_not_probed="candidate for credentialed API review; skip until keys and terms fit",
    ),
    AggregatorCandidate(
        platform="jooble",
        source_role="bounded_discovery_probe_candidate",
        hard_gate_status="probe_allowed_only_with_api_key_and_terms_review",
        access_path="documented REST API with key request",
        legal_terms_boundary="Use only within API terms and minimal evidence boundary.",
        automation_boundary="bounded API request, no detail pages, no DB writes",
        requires_credentials=True,
        credential_env_vars=("JOOBLE_API_KEY",),
        probe_strategy="jooble_rest_api",
        recommendation_when_not_probed="candidate for credentialed API review; watch broad aggregator noise",
    ),
    AggregatorCandidate(
        platform="remotive",
        source_role="market_signal_sampler_candidate",
        hard_gate_status="probe_allowed_with_public_api_and_attribution_boundary",
        access_path="public remote-jobs API",
        legal_terms_boundary="Respect attribution/linkback expectations; do not use as canonical local job database.",
        automation_boundary="bounded API request, no detail pages, no DB writes",
        requires_credentials=False,
        credential_env_vars=(),
        probe_strategy="remotive_public_api",
        recommendation_when_not_probed="run bounded API probe for remote-market signal only",
    ),
)


TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = html.unescape(str(value))
    text = TAG_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def normalized_lower(value: Any) -> str:
    return normalize_text(value).lower()


def matched_terms_for_job(job: dict[str, Any], search_terms: tuple[str, ...]) -> tuple[str, ...]:
    searchable_text = " ".join(
        normalized_lower(job.get(field))
        for field in (
            "title",
            "company",
            "company_name",
            "location",
            "description",
            "tags",
            "category",
        )
    )

    matched: list[str] = []
    for term in search_terms:
        normalized_term = normalized_lower(term)
        if not normalized_term:
            continue

        if normalized_term in searchable_text:
            matched.append(term)
            continue

        tokens = normalized_term.split()
        if tokens and all(token in searchable_text for token in tokens):
            matched.append(term)

    return tuple(matched)


def remote_signal_from_job(job: dict[str, Any]) -> str:
    if job.get("remote") is True:
        return "remote"

    text = " ".join(
        normalized_lower(job.get(field))
        for field in ("title", "location", "description", "tags", "job_type")
    )

    if "remote" in text or "home office" in text or "homeoffice" in text:
        return "remote"

    return "unknown"


def location_signal_for_match(match: JobMatch) -> str:
    text = f"{match.location} {match.title}".lower()
    signals: list[str] = []

    if "hannover" in text:
        signals.append("hannover")
    if "remote" in text or match.remote_signal == "remote":
        signals.append("remote")
    if "germany" in text or "deutschland" in text:
        signals.append("germany")
    if "berlin" in text:
        signals.append("berlin")

    return ",".join(signals) if signals else "unspecified"


def summarize_matches(matches: list[JobMatch]) -> tuple[int, str, str]:
    company_count = len({match.company for match in matches if match.company})

    term_counts: dict[str, int] = {}
    location_counts: dict[str, int] = {}

    for match in matches:
        for term in match.matched_terms:
            term_counts[term] = term_counts.get(term, 0) + 1
        signal = location_signal_for_match(match)
        location_counts[signal] = location_counts.get(signal, 0) + 1

    matched_terms = "; ".join(
        f"{term}={count}" for term, count in sorted(term_counts.items())
    ) or "<none>"
    location_signals = "; ".join(
        f"{signal}={count}" for signal, count in sorted(location_counts.items())
    ) or "<none>"

    return company_count, matched_terms, location_signals


def request_json(
    session: requests.Session,
    url: str,
    *,
    timeout_seconds: int,
    method: str = "GET",
    json_payload: dict[str, Any] | None = None,
) -> Any:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    if method == "POST":
        response = session.post(
            url,
            json=json_payload,
            timeout=timeout_seconds,
            headers=headers,
        )
    else:
        response = session.get(url, timeout=timeout_seconds, headers=headers)

    response.raise_for_status()
    return response.json()


def parse_arbeitnow_jobs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = payload.get("data", [])
    if not isinstance(jobs, list):
        return []

    parsed: list[dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        parsed.append(
            {
                "source_job_id": normalize_text(job.get("slug")),
                "title": normalize_text(job.get("title")),
                "company": normalize_text(job.get("company_name")),
                "location": normalize_text(job.get("location")),
                "remote": job.get("remote"),
                "url": normalize_text(job.get("url")),
                "description": normalize_text(job.get("description")),
                "tags": " ".join(normalize_text(tag) for tag in job.get("tags", []) if tag),
            }
        )
    return parsed


def parse_remotive_jobs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = payload.get("jobs", [])
    if not isinstance(jobs, list):
        return []

    parsed: list[dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        parsed.append(
            {
                "source_job_id": normalize_text(job.get("id")),
                "title": normalize_text(job.get("title")),
                "company": normalize_text(job.get("company_name")),
                "location": normalize_text(job.get("candidate_required_location")),
                "remote": True,
                "url": normalize_text(job.get("url")),
                "description": normalize_text(job.get("description")),
                "category": normalize_text(job.get("category")),
            }
        )
    return parsed


def parse_adzuna_jobs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = payload.get("results", [])
    if not isinstance(jobs, list):
        return []

    parsed: list[dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        company = job.get("company", {})
        location = job.get("location", {})
        parsed.append(
            {
                "source_job_id": normalize_text(job.get("id")),
                "title": normalize_text(job.get("title")),
                "company": normalize_text(company.get("display_name") if isinstance(company, dict) else company),
                "location": normalize_text(location.get("display_name") if isinstance(location, dict) else location),
                "remote": None,
                "url": normalize_text(job.get("redirect_url")),
                "description": normalize_text(job.get("description")),
            }
        )
    return parsed


def parse_jooble_jobs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = payload.get("jobs", [])
    if not isinstance(jobs, list):
        return []

    parsed: list[dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        parsed.append(
            {
                "source_job_id": normalize_text(job.get("id")),
                "title": normalize_text(job.get("title")),
                "company": normalize_text(job.get("company")),
                "location": normalize_text(job.get("location")),
                "remote": None,
                "url": normalize_text(job.get("link")),
                "description": normalize_text(job.get("snippet")),
            }
        )
    return parsed


def jobs_to_matches(
    *,
    platform: str,
    query: str,
    jobs: list[dict[str, Any]],
    search_terms: tuple[str, ...],
    max_matches_per_source: int,
) -> list[JobMatch]:
    if max_matches_per_source <= 0:
        return []

    matches: list[JobMatch] = []

    for job in jobs:
        matched_terms = matched_terms_for_job(job, search_terms)
        if not matched_terms:
            continue

        matches.append(
            JobMatch(
                platform=platform,
                query=query,
                title=normalize_text(job.get("title")),
                company=normalize_text(job.get("company")),
                location=normalize_text(job.get("location")),
                remote_signal=remote_signal_from_job(job),
                url=normalize_text(job.get("url")),
                source_job_id=normalize_text(job.get("source_job_id")),
                matched_terms=matched_terms,
            )
        )

        if len(matches) >= max_matches_per_source:
            break

    return matches


def probe_arbeitnow(
    session: requests.Session,
    *,
    search_terms: tuple[str, ...],
    timeout_seconds: int,
    max_matches_per_source: int,
    max_pages: int,
    location: str,
    country_code: str,
) -> tuple[int, int, list[JobMatch], list[str]]:
    del location, country_code

    matches: list[JobMatch] = []
    notes: list[str] = []
    total_returned = 0
    request_count = 0

    for page in range(1, max_pages + 1):
        url = "https://www.arbeitnow.com/api/job-board-api"
        if page > 1:
            url = f"{url}?{urlencode({'page': page})}"

        payload = request_json(session, url, timeout_seconds=timeout_seconds)
        request_count += 1
        jobs = parse_arbeitnow_jobs(payload)
        total_returned += len(jobs)
        matches.extend(
            jobs_to_matches(
                platform="arbeitnow",
                query=f"local_filter_page={page}",
                jobs=jobs,
                search_terms=search_terms,
                max_matches_per_source=max_matches_per_source - len(matches),
            )
        )

        if len(matches) >= max_matches_per_source:
            notes.append("match_export_limit_reached")
            break

        if page < max_pages:
            time.sleep(REQUEST_SLEEP_SECONDS)

    return request_count, total_returned, matches, notes


def probe_remotive(
    session: requests.Session,
    *,
    search_terms: tuple[str, ...],
    timeout_seconds: int,
    max_matches_per_source: int,
    max_pages: int,
    location: str,
    country_code: str,
) -> tuple[int, int, list[JobMatch], list[str]]:
    del max_pages, location, country_code

    matches: list[JobMatch] = []
    notes: list[str] = []
    total_returned = 0
    request_count = 0

    for term in search_terms:
        url = f"https://remotive.com/api/remote-jobs?{urlencode({'search': term})}"
        payload = request_json(session, url, timeout_seconds=timeout_seconds)
        request_count += 1
        jobs = parse_remotive_jobs(payload)
        total_returned += len(jobs)
        matches.extend(
            jobs_to_matches(
                platform="remotive",
                query=term,
                jobs=jobs,
                search_terms=search_terms,
                max_matches_per_source=max_matches_per_source - len(matches),
            )
        )

        if len(matches) >= max_matches_per_source:
            notes.append("match_export_limit_reached")
            break

        time.sleep(REQUEST_SLEEP_SECONDS)

    return request_count, total_returned, matches, notes


def probe_adzuna(
    session: requests.Session,
    *,
    search_terms: tuple[str, ...],
    timeout_seconds: int,
    max_matches_per_source: int,
    max_pages: int,
    location: str,
    country_code: str,
) -> tuple[int, int, list[JobMatch], list[str]]:
    del max_pages

    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return 0, 0, [], ["missing_credentials:ADZUNA_APP_ID,ADZUNA_APP_KEY"]

    matches: list[JobMatch] = []
    notes: list[str] = []
    total_returned = 0
    request_count = 0

    for term in search_terms:
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "what": term,
            "where": location,
            "results_per_page": 20,
            "content-type": "application/json",
        }
        url = f"https://api.adzuna.com/v1/api/jobs/{country_code}/search/1?{urlencode(params)}"
        payload = request_json(session, url, timeout_seconds=timeout_seconds)
        request_count += 1
        jobs = parse_adzuna_jobs(payload)
        total_returned += len(jobs)
        matches.extend(
            jobs_to_matches(
                platform="adzuna",
                query=f"{term} / {location}",
                jobs=jobs,
                search_terms=search_terms,
                max_matches_per_source=max_matches_per_source - len(matches),
            )
        )

        if len(matches) >= max_matches_per_source:
            notes.append("match_export_limit_reached")
            break

        time.sleep(REQUEST_SLEEP_SECONDS)

    return request_count, total_returned, matches, notes


def probe_jooble(
    session: requests.Session,
    *,
    search_terms: tuple[str, ...],
    timeout_seconds: int,
    max_matches_per_source: int,
    max_pages: int,
    location: str,
    country_code: str,
) -> tuple[int, int, list[JobMatch], list[str]]:
    del max_pages, country_code

    api_key = os.getenv("JOOBLE_API_KEY")
    if not api_key:
        return 0, 0, [], ["missing_credentials:JOOBLE_API_KEY"]

    matches: list[JobMatch] = []
    notes: list[str] = []
    total_returned = 0
    request_count = 0
    url = f"https://jooble.org/api/{api_key}"

    for term in search_terms:
        payload = request_json(
            session,
            url,
            timeout_seconds=timeout_seconds,
            method="POST",
            json_payload={"keywords": term, "location": location},
        )
        request_count += 1
        jobs = parse_jooble_jobs(payload)
        total_returned += len(jobs)
        matches.extend(
            jobs_to_matches(
                platform="jooble",
                query=f"{term} / {location}",
                jobs=jobs,
                search_terms=search_terms,
                max_matches_per_source=max_matches_per_source - len(matches),
            )
        )

        if len(matches) >= max_matches_per_source:
            notes.append("match_export_limit_reached")
            break

        time.sleep(REQUEST_SLEEP_SECONDS)

    return request_count, total_returned, matches, notes


PROBE_FUNCTIONS: dict[str, Callable[..., tuple[int, int, list[JobMatch], list[str]]]] = {
    "arbeitnow_public_api": probe_arbeitnow,
    "remotive_public_api": probe_remotive,
    "adzuna_search_api": probe_adzuna,
    "jooble_rest_api": probe_jooble,
}


def evaluate_candidate(
    candidate: AggregatorCandidate,
    *,
    session: requests.Session,
    search_terms: tuple[str, ...],
    timeout_seconds: int,
    max_matches_per_source: int,
    max_pages: int,
    location: str,
    country_code: str,
) -> tuple[CandidateEvaluation, list[JobMatch]]:
    probe_function = PROBE_FUNCTIONS.get(candidate.probe_strategy)

    if probe_function is None:
        return (
            CandidateEvaluation(
                platform=candidate.platform,
                source_role=candidate.source_role,
                hard_gate_status=candidate.hard_gate_status,
                access_path=candidate.access_path,
                legal_terms_boundary=candidate.legal_terms_boundary,
                automation_boundary=candidate.automation_boundary,
                requires_credentials=candidate.requires_credentials,
                credential_env_vars=", ".join(candidate.credential_env_vars) or "<none>",
                probe_strategy=candidate.probe_strategy,
                probe_status="not_probed_by_design",
                probe_method="none",
                request_count=0,
                total_returned=0,
                matching_jobs=0,
                matching_companies=0,
                matched_terms="<none>",
                location_signal_counts="<none>",
                recommendation=candidate.recommendation_when_not_probed,
                notes="hard-gated or existing source; no network request issued",
            ),
            [],
        )

    try:
        request_count, total_returned, matches, notes = probe_function(
            session,
            search_terms=search_terms,
            timeout_seconds=timeout_seconds,
            max_matches_per_source=max_matches_per_source,
            max_pages=max_pages,
            location=location,
            country_code=country_code,
        )
    except requests.RequestException as error:
        return (
            CandidateEvaluation(
                platform=candidate.platform,
                source_role=candidate.source_role,
                hard_gate_status=candidate.hard_gate_status,
                access_path=candidate.access_path,
                legal_terms_boundary=candidate.legal_terms_boundary,
                automation_boundary=candidate.automation_boundary,
                requires_credentials=candidate.requires_credentials,
                credential_env_vars=", ".join(candidate.credential_env_vars) or "<none>",
                probe_strategy=candidate.probe_strategy,
                probe_status="probe_failed",
                probe_method="bounded_api_request",
                request_count=0,
                total_returned=0,
                matching_jobs=0,
                matching_companies=0,
                matched_terms="<none>",
                location_signal_counts="<none>",
                recommendation="do_not_activate; inspect failure before further evaluation",
                notes=f"request_error:{type(error).__name__}:{error}",
            ),
            [],
        )

    credential_note = next((note for note in notes if note.startswith("missing_credentials:")), None)
    if credential_note:
        probe_status = "skipped_missing_credentials"
        recommendation = candidate.recommendation_when_not_probed
    elif matches:
        probe_status = "probed_with_matches"
        recommendation = "review_matches_for_employer_origin_or_ats_candidates"
    else:
        probe_status = "probed_without_matches"
        recommendation = "do_not_activate_now; retain as candidate only if strategic value remains"

    company_count, matched_terms, location_signals = summarize_matches(matches)

    return (
        CandidateEvaluation(
            platform=candidate.platform,
            source_role=candidate.source_role,
            hard_gate_status=candidate.hard_gate_status,
            access_path=candidate.access_path,
            legal_terms_boundary=candidate.legal_terms_boundary,
            automation_boundary=candidate.automation_boundary,
            requires_credentials=candidate.requires_credentials,
            credential_env_vars=", ".join(candidate.credential_env_vars) or "<none>",
            probe_strategy=candidate.probe_strategy,
            probe_status=probe_status,
            probe_method="bounded_api_request",
            request_count=request_count,
            total_returned=total_returned,
            matching_jobs=len(matches),
            matching_companies=company_count,
            matched_terms=matched_terms,
            location_signal_counts=location_signals,
            recommendation=recommendation,
            notes="; ".join(notes) if notes else "minimal evidence only; no descriptions exported; no DB writes",
        ),
        matches,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_safe_row(row: Any) -> dict[str, Any]:
    data = asdict(row) if not isinstance(row, dict) else row

    return {
        key: "; ".join(value) if isinstance(value, tuple) else value
        for key, value in data.items()
    }


def write_csv(path: Path, rows: list[Any], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(csv_safe_row(row))


def build_manifest(
    *,
    evaluations: list[CandidateEvaluation],
    matches: list[JobMatch],
    summary_path: Path,
    matches_path: Path,
    search_terms: tuple[str, ...],
    location: str,
    country_code: str,
) -> dict[str, Any]:
    return {
        "mode": "bounded_aggregator_discovery_candidate_evaluation",
        "database_writes": False,
        "detail_pages_fetched": False,
        "raw_content_persistence": "minimal_evidence_only_no_descriptions_exported",
        "search_terms": list(search_terms),
        "location": location,
        "country_code": country_code,
        "candidate_count": len(evaluations),
        "hard_gated_or_existing_not_probed_count": sum(
            1 for item in evaluations if item.probe_status == "not_probed_by_design"
        ),
        "probed_count": sum(
            1 for item in evaluations if item.probe_status.startswith("probed_")
        ),
        "skipped_missing_credentials_count": sum(
            1 for item in evaluations if item.probe_status == "skipped_missing_credentials"
        ),
        "probe_failed_count": sum(
            1 for item in evaluations if item.probe_status == "probe_failed"
        ),
        "matching_jobs_total": len(matches),
        "matching_companies_total": len({match.company for match in matches if match.company}),
        "source_fragmentation_interpretation": (
            "Current source overlap is low; each source may add value, but large aggregators "
            "cannot be assumed to provide defensible broad coverage under the project gates. "
            "Employer-origin and ATS-near sources remain the preferred way to improve coverage."
        ),
        "output_files": {
            "summary_csv": str(summary_path),
            "matches_csv": str(matches_path),
        },
        "output_sha256": {
            "summary_csv": sha256_file(summary_path),
            "matches_csv": sha256_file(matches_path),
        },
    }


def run_evaluation(
    *,
    export_dir: Path,
    search_terms: tuple[str, ...],
    timeout_seconds: int,
    max_matches_per_source: int,
    max_pages: int,
    location: str,
    country_code: str,
) -> dict[str, Any]:
    export_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    evaluations: list[CandidateEvaluation] = []
    all_matches: list[JobMatch] = []

    for candidate in CANDIDATES:
        evaluation, matches = evaluate_candidate(
            candidate,
            session=session,
            search_terms=search_terms,
            timeout_seconds=timeout_seconds,
            max_matches_per_source=max_matches_per_source,
            max_pages=max_pages,
            location=location,
            country_code=country_code,
        )
        evaluations.append(evaluation)
        all_matches.extend(matches)

    summary_path = export_dir / "aggregator_discovery_candidate_evaluation.csv"
    matches_path = export_dir / "aggregator_discovery_candidate_matches.csv"
    manifest_path = export_dir / "aggregator_discovery_candidate_manifest.json"

    write_csv(
        summary_path,
        evaluations,
        [
            "platform",
            "source_role",
            "hard_gate_status",
            "access_path",
            "legal_terms_boundary",
            "automation_boundary",
            "requires_credentials",
            "credential_env_vars",
            "probe_strategy",
            "probe_status",
            "probe_method",
            "request_count",
            "total_returned",
            "matching_jobs",
            "matching_companies",
            "matched_terms",
            "location_signal_counts",
            "recommendation",
            "notes",
        ],
    )

    write_csv(
        matches_path,
        all_matches,
        [
            "platform",
            "query",
            "title",
            "company",
            "location",
            "remote_signal",
            "url",
            "source_job_id",
            "matched_terms",
        ],
    )

    manifest = build_manifest(
        evaluations=evaluations,
        matches=all_matches,
        summary_path=summary_path,
        matches_path=matches_path,
        search_terms=search_terms,
        location=location,
        country_code=country_code,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    print("Aggregator Discovery Candidate Evaluation")
    print("Mode: bounded defensive source-family evaluation")
    print("Database writes: none")
    print("Detail pages fetched: none")
    print("Raw content persistence: minimal evidence only, no descriptions exported")
    print()

    for evaluation in evaluations:
        print("---")
        print("platform:", evaluation.platform)
        print("source_role:", evaluation.source_role)
        print("hard_gate_status:", evaluation.hard_gate_status)
        print("probe_status:", evaluation.probe_status)
        print("request_count:", evaluation.request_count)
        print("total_returned:", evaluation.total_returned)
        print("matching_jobs:", evaluation.matching_jobs)
        print("matching_companies:", evaluation.matching_companies)
        print("matched_terms:", evaluation.matched_terms)
        print("location_signal_counts:", evaluation.location_signal_counts)
        print("recommendation:", evaluation.recommendation)

    print()
    print("Interpretation boundary:")
    print("- This script evaluates aggregator candidates; it is not a connector.")
    print("- It does not write raw_jobs, source_value_snapshots or search profiles.")
    print("- Hard-gated platforms remain research-only/reference-only unless a suitable approved path exists.")
    print("- API-friendly candidates are only probes; positive matches are employer-origin/ATS discovery leads.")
    print()
    print("Exported aggregator discovery files:")
    print(f"- {summary_path}")
    print(f"- {matches_path}")
    print(f"- {manifest_path}")

    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate aggregator/discovery candidates without DB writes.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/aggregator_discovery_candidate_evaluation"),
    )
    parser.add_argument(
        "--search-term",
        action="append",
        dest="search_terms",
        help="Search term to evaluate. Can be passed multiple times.",
    )
    parser.add_argument(
        "--location",
        default=DEFAULT_LOCATION,
        help="Location for APIs that support a location parameter.",
    )
    parser.add_argument(
        "--country-code",
        default=DEFAULT_COUNTRY_CODE,
        help="Country code for APIs that require one, e.g. Adzuna.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--max-matches-per-source",
        type=int,
        default=25,
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Maximum pages for APIs with simple pagination support.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    search_terms = tuple(args.search_terms or DEFAULT_SEARCH_TERMS)

    run_evaluation(
        export_dir=args.export_dir,
        search_terms=search_terms,
        timeout_seconds=args.timeout_seconds,
        max_matches_per_source=args.max_matches_per_source,
        max_pages=args.max_pages,
        location=args.location,
        country_code=args.country_code,
    )


if __name__ == "__main__":
    main()
