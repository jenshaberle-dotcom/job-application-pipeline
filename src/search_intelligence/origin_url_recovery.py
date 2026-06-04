"""Bounded employer-origin source URL recovery helpers.

The recovery step is intentionally narrow: it generates a small set of public,
company-related career/job URL candidates from the persisted employer-origin
candidate and probes them with normal HTTP GET requests. It does not use search
engines, does not build/register connectors, does not activate sources and does
not write Bronze records.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Iterable, Sequence
from urllib.parse import urlparse

from src.search_intelligence.origin_url_policy import has_disallowed_source_url_shape

CAREER_PATHS = (
    "/jobs/",
    "/job/",
    "/careers/",
    "/career/",
    "/karriere/",
    "/karriere/jobs/",
    "/de/karriere/jobs/",
    "/de/karriere/stellenangebote/",
)

JOB_HOST_PREFIXES = ("jobs", "careers", "career", "karriere")
RECOVERY_ACCEPTED_STATUS_CODES = range(200, 400)
JOB_SIGNAL_TERMS = (
    "job",
    "jobs",
    "career",
    "careers",
    "karriere",
    "stellen",
    "stellenangebote",
    "vacancies",
)


@dataclass(frozen=True)
class RecoveryProbeResult:
    url: str
    final_url: str | None
    status_code: int | None
    accepted: bool
    reason: str
    title: str | None = None
    response_bytes: int = 0


def _normalize_token(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    parts = [part for part in re.split(r"[^a-z0-9]+", raw) if len(part) >= 3]
    return parts[0] if parts else ""


def _host_without_www(hostname: str | None) -> str:
    host = str(hostname or "").strip().lower()
    return host[4:] if host.startswith("www.") else host


def _registered_like_domain(hostname: str | None) -> str:
    host = _host_without_www(hostname)
    parts = [part for part in host.split(".") if part]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def _scheme(url: str) -> str:
    parsed = urlparse(url)
    return parsed.scheme if parsed.scheme in {"http", "https"} else "https"


def _append_candidate(candidates: list[str], seen: set[str], url: str) -> None:
    normalized = url.strip()
    if not normalized:
        return
    if has_disallowed_source_url_shape(normalized) is not None:
        return
    if normalized in seen:
        return
    seen.add(normalized)
    candidates.append(normalized)


def generate_recovery_url_candidates(
    *,
    company_key: str,
    company_name: str | None,
    source_family_candidate: str | None,
    current_url: str,
    max_candidates: int = 12,
) -> tuple[str, ...]:
    """Generate a bounded list of plausible public employer-origin URLs.

    The list is deterministic and company-related. It includes common ATS/job host
    patterns such as ``jobs.<company>-group.com`` because real employer-origin
    setups often use a separate job host while the public career landing page
    lives under the corporate domain.
    """

    parsed = urlparse(current_url)
    current_host = _host_without_www(parsed.hostname)
    registered = _registered_like_domain(parsed.hostname)
    scheme = _scheme(current_url)

    tokens = [
        _normalize_token(company_key),
        _normalize_token(source_family_candidate),
        _normalize_token(company_name),
    ]
    company_token = next((token for token in tokens if token), "")

    candidates: list[str] = []
    seen: set[str] = set()

    # Prefer job-host patterns first for 404 landing-page failures. For adesso,
    # this yields https://jobs.adesso-group.com/ without hard-coding the company.
    if company_token:
        for host in (
            f"jobs.{company_token}-group.com",
            f"careers.{company_token}-group.com",
            f"jobs.{company_token}.com",
            f"careers.{company_token}.com",
            f"jobs.{company_token}.de",
            f"careers.{company_token}.de",
            f"karriere.{company_token}.de",
        ):
            _append_candidate(candidates, seen, f"https://{host}/")

    for host in (current_host, registered):
        if not host:
            continue
        for path in CAREER_PATHS:
            _append_candidate(candidates, seen, f"{scheme}://{host}{path}")
            _append_candidate(candidates, seen, f"https://{host}{path}")

    return tuple(candidates[:max_candidates])


def _looks_like_job_or_career_url(url: str, body: str = "") -> bool:
    haystack = f"{url} {body[:5000]}".lower()
    return any(term in haystack for term in JOB_SIGNAL_TERMS)


def select_recovery_url(
    candidates: Sequence[str],
    *,
    probe: Callable[[str], RecoveryProbeResult],
) -> tuple[str | None, tuple[RecoveryProbeResult, ...]]:
    """Probe candidates in order and select the first reachable career-like URL."""

    results: list[RecoveryProbeResult] = []
    for url in candidates:
        result = probe(url)
        results.append(result)
        if result.accepted:
            return url, tuple(results)
    return None, tuple(results)


def probe_result_from_http_response(url: str, response: object) -> RecoveryProbeResult:
    """Build a recovery result from a requests-like response object."""

    status_code = int(getattr(response, "status_code", 0) or 0)
    final_url = str(getattr(response, "url", "") or url)
    content = getattr(response, "content", b"") or b""
    text = str(getattr(response, "text", "") or "")
    accepted_status = status_code in RECOVERY_ACCEPTED_STATUS_CODES
    career_like = _looks_like_job_or_career_url(final_url, text)
    accepted = accepted_status and career_like
    reason = "reachable career/job-like URL" if accepted else f"status={status_code}; career_like={career_like}"
    return RecoveryProbeResult(
        url=url,
        final_url=final_url,
        status_code=status_code,
        accepted=accepted,
        reason=reason,
        response_bytes=len(content),
    )
