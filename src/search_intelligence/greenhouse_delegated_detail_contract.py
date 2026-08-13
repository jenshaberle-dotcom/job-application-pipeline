"""Greenhouse-only delegated detail authority for employer-origin repair.

This module is deliberately narrow.  A Greenhouse hostname or board token never
establishes employer identity by itself.  Delegation is authorized only when a
fresh employer-origin page exposes a first-party Greenhouse board reference and
the corresponding public Greenhouse board object returns an organization name
that exactly matches one distinctive canonical employer token.

The returned jobs are still only *candidates*.  The Detail Evidence repair agent
must apply its existing concrete-detail, profile and target-location validation
before a gate can pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import re
from typing import Any, Callable, Mapping
from urllib.parse import urljoin, urlparse

import requests

import src.search_intelligence.origin_source_discovery_agent as origin_agent


GREENHOUSE_DELEGATED_AUTHORITY_KIND = "greenhouse_first_party_board"
GREENHOUSE_AUTHORITY_CONTRACT_VERSION = "GREENHOUSE-DELEGATION-001"
REQUEST_TIMEOUT_SECONDS = 20

# Product authority is deliberately smaller than the historical Greenhouse
# validation inventory.  #47 is the only employer whose full current authority
# chain has been proven under Pipeline #514.
REVIEWED_GREENHOUSE_BOARD_TOKENS: Mapping[str, str] = {
    "commercetools": "commercetools",
}

_GREENHOUSE_REFERENCE_HOSTS = {
    "boards-api.greenhouse.io",
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
}
_COMMON_LANGUAGE_TOKENS = {"and", "und", "the", "der", "die", "das"}


@dataclass(frozen=True)
class GreenhouseDelegatedJob:
    external_job_id: str
    title: str
    location: str
    absolute_url: str


@dataclass(frozen=True)
class GreenhouseDelegationResolution:
    attempted: bool
    authorized: bool
    status: str
    board_token: str | None
    board_name: str | None
    board_jobs_url: str | None
    jobs: tuple[GreenhouseDelegatedJob, ...]
    evidence: dict[str, Any]


JsonFetcher = Callable[[str], tuple[dict[str, Any], str, int]]


def fetch_greenhouse_json(url: str) -> tuple[dict[str, Any], str, int]:
    """Fetch one bounded first-party Greenhouse JSON resource."""

    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "job-application-pipeline-greenhouse-delegated-detail/0.1 "
                "(bounded; first-party; no raw html persistence)"
            ),
            "Accept": "application/json,*/*;q=0.1",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
        allow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Greenhouse response must be a JSON object")
    return payload, response.url, response.status_code


def _decoded_reference_text(html: str) -> str:
    value = unescape(html or "")
    value = value.replace(r"\/", "/")
    value = value.replace(r"\u002F", "/").replace(r"\u002f", "/")
    return value


def extract_greenhouse_reference_hosts(html: str, base_url: str) -> tuple[str, ...]:
    """Return concrete first-party Greenhouse board hosts exposed by page HTML.

    A plain word such as ``greenhouse`` is intentionally insufficient.  The
    employer page must contain an actual absolute/protocol-relative URL pointing
    at a recognized Greenhouse board surface.
    """

    decoded = _decoded_reference_text(html)
    seen: set[str] = set()
    result: list[str] = []
    for match in re.finditer(r"(?:https?:)?//[^\s\"'<>\\]+", decoded, flags=re.IGNORECASE):
        raw_url = match.group(0).rstrip("),;]")
        url = urljoin(base_url, raw_url)
        parsed = urlparse(url)
        host = (parsed.hostname or "").casefold()
        if host not in _GREENHOUSE_REFERENCE_HOSTS:
            continue
        path = re.sub(r"/{2,}", "/", parsed.path or "/").casefold()
        if host == "boards-api.greenhouse.io" and "/v1/boards/" not in f"{path}/":
            continue
        if host != "boards-api.greenhouse.io" and not path.strip("/"):
            continue
        if host not in seen:
            seen.add(host)
            result.append(host)
    return tuple(result)


def distinctive_company_tokens(company_name: str) -> tuple[str, ...]:
    """Reuse the Pipeline's existing canonical distinctive-token semantics."""

    return tuple(
        token
        for token in origin_agent.tokenize(company_name)
        if len(token) >= 5
        and token not in origin_agent.LEGAL_OR_GENERIC_TOKENS
        and token not in origin_agent.LOCALITY_TOKENS
        and token not in _COMMON_LANGUAGE_TOKENS
    )


def board_name_matches_company(*, board_name: str, company_name: str) -> bool:
    board_tokens = tuple(origin_agent.tokenize(board_name))
    return bool(
        len(board_tokens) == 1
        and board_tokens[0] in distinctive_company_tokens(company_name)
    )


def greenhouse_job_url_token_consistent(url: str, board_token: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    if host not in {"boards.greenhouse.io", "job-boards.greenhouse.io"}:
        return False

    parts = [part.casefold() for part in parsed.path.split("/") if part]
    token = board_token.casefold()
    if token not in parts:
        return False
    token_index = parts.index(token)
    try:
        jobs_index = parts.index("jobs", token_index + 1)
    except ValueError:
        return False
    if jobs_index + 1 >= len(parts):
        return False
    job_identity = parts[jobs_index + 1]
    return bool(re.fullmatch(r"[0-9]{4,}", job_identity))


def _normalize_job_location(job: Mapping[str, Any]) -> str:
    location = job.get("location")
    if isinstance(location, dict):
        name = str(location.get("name") or "").strip()
        if name:
            return name
    elif isinstance(location, str) and location.strip():
        return location.strip()

    offices = job.get("offices")
    if isinstance(offices, list):
        names = [
            str(item.get("name") or "").strip()
            for item in offices
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
        if names:
            return ", ".join(names)
    return ""


def _result(
    *,
    attempted: bool,
    authorized: bool,
    status: str,
    board_token: str | None,
    board_name: str | None,
    board_jobs_url: str | None,
    jobs: tuple[GreenhouseDelegatedJob, ...] = (),
    evidence: Mapping[str, Any],
) -> GreenhouseDelegationResolution:
    return GreenhouseDelegationResolution(
        attempted=attempted,
        authorized=authorized,
        status=status,
        board_token=board_token,
        board_name=board_name,
        board_jobs_url=board_jobs_url,
        jobs=jobs,
        evidence=dict(evidence),
    )


def resolve_greenhouse_delegation(
    *,
    company_key: str,
    company_name: str,
    fresh_reference_hosts: tuple[str, ...],
    json_fetcher: JsonFetcher = fetch_greenhouse_json,
) -> GreenhouseDelegationResolution:
    """Resolve one bounded Greenhouse board into authorized job candidates.

    Network behavior after routing is bounded to one board-metadata request and,
    only after identity succeeds, one board-jobs request.
    """

    base_evidence: dict[str, Any] = {
        "contract_version": GREENHOUSE_AUTHORITY_CONTRACT_VERSION,
        "authority_kind": GREENHOUSE_DELEGATED_AUTHORITY_KIND,
        "fresh_reference_hosts": list(fresh_reference_hosts),
        "hostname_or_token_alone_authoritative": False,
        "board_metadata_requests": 0,
        "board_jobs_requests": 0,
        "raw_html_persisted": False,
    }

    if not fresh_reference_hosts:
        return _result(
            attempted=False,
            authorized=False,
            status="missing_fresh_employer_greenhouse_reference",
            board_token=None,
            board_name=None,
            board_jobs_url=None,
            evidence=base_evidence,
        )

    if not set(fresh_reference_hosts).issubset(_GREENHOUSE_REFERENCE_HOSTS):
        return _result(
            attempted=False,
            authorized=False,
            status="unrecognized_greenhouse_reference_host",
            board_token=None,
            board_name=None,
            board_jobs_url=None,
            evidence=base_evidence,
        )

    board_token = REVIEWED_GREENHOUSE_BOARD_TOKENS.get(company_key)
    if not board_token:
        return _result(
            attempted=False,
            authorized=False,
            status="no_reviewed_greenhouse_board_token",
            board_token=None,
            board_name=None,
            board_jobs_url=None,
            evidence=base_evidence,
        )

    metadata_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}"
    jobs_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
    base_evidence.update(
        {
            "board_token": board_token,
            "board_metadata_url": metadata_url,
            "board_jobs_url": jobs_url,
            "distinctive_canonical_company_tokens": list(distinctive_company_tokens(company_name)),
        }
    )

    try:
        metadata, metadata_final_url, metadata_status = json_fetcher(metadata_url)
    except Exception as exc:  # noqa: BLE001 - fail closed per delegated board.
        base_evidence["board_metadata_requests"] = 1
        base_evidence["metadata_error"] = type(exc).__name__
        return _result(
            attempted=True,
            authorized=False,
            status="board_metadata_fetch_failed",
            board_token=board_token,
            board_name=None,
            board_jobs_url=jobs_url,
            evidence=base_evidence,
        )

    base_evidence["board_metadata_requests"] = 1
    base_evidence["board_metadata_status_code"] = metadata_status
    base_evidence["board_metadata_final_host"] = (urlparse(metadata_final_url).hostname or "").casefold()
    if metadata_status >= 400 or base_evidence["board_metadata_final_host"] != "boards-api.greenhouse.io":
        return _result(
            attempted=True,
            authorized=False,
            status="board_metadata_not_first_party_reachable",
            board_token=board_token,
            board_name=None,
            board_jobs_url=jobs_url,
            evidence=base_evidence,
        )

    board_name = str(metadata.get("name") or "").strip()
    base_evidence["board_name"] = board_name
    base_evidence["board_name_tokens"] = list(origin_agent.tokenize(board_name))
    identity_match = board_name_matches_company(board_name=board_name, company_name=company_name)
    base_evidence["board_identity_proven"] = identity_match
    if not identity_match:
        return _result(
            attempted=True,
            authorized=False,
            status="board_identity_failed",
            board_token=board_token,
            board_name=board_name or None,
            board_jobs_url=jobs_url,
            evidence=base_evidence,
        )

    try:
        jobs_payload, jobs_final_url, jobs_status = json_fetcher(jobs_url)
    except Exception as exc:  # noqa: BLE001 - fail closed per delegated board.
        base_evidence["board_jobs_requests"] = 1
        base_evidence["jobs_error"] = type(exc).__name__
        return _result(
            attempted=True,
            authorized=False,
            status="board_jobs_fetch_failed",
            board_token=board_token,
            board_name=board_name,
            board_jobs_url=jobs_url,
            evidence=base_evidence,
        )

    base_evidence["board_jobs_requests"] = 1
    base_evidence["board_jobs_status_code"] = jobs_status
    base_evidence["board_jobs_final_host"] = (urlparse(jobs_final_url).hostname or "").casefold()
    if jobs_status >= 400 or base_evidence["board_jobs_final_host"] != "boards-api.greenhouse.io":
        return _result(
            attempted=True,
            authorized=False,
            status="board_jobs_not_first_party_reachable",
            board_token=board_token,
            board_name=board_name,
            board_jobs_url=jobs_url,
            evidence=base_evidence,
        )

    raw_jobs = jobs_payload.get("jobs")
    if not isinstance(raw_jobs, list):
        raw_jobs = []

    jobs: list[GreenhouseDelegatedJob] = []
    rejected_job_urls: list[str] = []
    for raw_job in raw_jobs:
        if not isinstance(raw_job, dict):
            continue
        absolute_url = str(raw_job.get("absolute_url") or "").strip()
        if not greenhouse_job_url_token_consistent(absolute_url, board_token):
            if absolute_url:
                rejected_job_urls.append(absolute_url)
            continue
        external_job_id = str(raw_job.get("id") or "").strip()
        if not external_job_id:
            continue
        jobs.append(
            GreenhouseDelegatedJob(
                external_job_id=external_job_id,
                title=str(raw_job.get("title") or "").strip(),
                location=_normalize_job_location(raw_job),
                absolute_url=absolute_url,
            )
        )

    base_evidence["raw_job_count"] = len(raw_jobs)
    base_evidence["token_consistent_job_count"] = len(jobs)
    base_evidence["rejected_job_url_count"] = len(rejected_job_urls)
    return _result(
        attempted=True,
        authorized=True,
        status="board_authorized",
        board_token=board_token,
        board_name=board_name,
        board_jobs_url=jobs_url,
        jobs=tuple(jobs),
        evidence=base_evidence,
    )
