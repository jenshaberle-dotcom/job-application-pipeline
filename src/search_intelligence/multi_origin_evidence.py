"""Multi-origin evidence discovery helpers for employer-origin candidates.

The goal is to avoid a propagated pipeline failure where the system chooses one
plausible career URL too early and then concludes that no detail evidence exists.
This module keeps URL discovery, classification, confidence and failure taxonomy
small, deterministic and testable. It deliberately does not persist data and does
not perform network I/O; scripts pass discovered/fetched URLs into these helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from re import search, sub
from typing import Iterable
from urllib.parse import parse_qs, unquote, urljoin, urlparse, urlunparse


class EvidenceDecision(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    IMPLEMENTATION_GAP = "implementation_gap"


class EvidenceFailureReason(StrEnum):
    URL_NOT_REACHABLE = "url_not_reachable"
    DOMAIN_NOT_PLAUSIBLE = "domain_not_plausible"
    GENERIC_CAREER_PAGE_ONLY = "generic_career_page_only"
    NO_JOB_LIST_FOUND = "no_job_list_found"
    JOB_LIST_FOUND_BUT_NO_DETAIL_LINKS = "job_list_found_but_no_detail_links"
    DETAIL_LINKS_FOUND_BUT_EXTRACTOR_UNSUPPORTED = "detail_links_found_but_extractor_unsupported"
    DETAIL_PAGE_EXTRACTED_BUT_NO_PROFILE_SIGNAL = "detail_page_extracted_but_no_profile_signal"
    DETAIL_PAGE_EXTRACTED_BUT_NO_TARGET_SIGNAL = "detail_page_extracted_but_no_target_signal"
    PROFILE_AND_TARGET_SIGNAL_FOUND = "profile_and_target_signal_found"


@dataclass(frozen=True)
class UrlEvidenceCandidate:
    """One URL that should be considered during evidence discovery."""

    url: str
    discovery_source: str
    confidence_hint: float
    reason: str


@dataclass(frozen=True)
class SearchDiscoveryQuery:
    """One planned search-engine query for the discovery stage."""

    query: str
    reason: str


@dataclass(frozen=True)
class UrlAssessment:
    """Classification of a single checked URL/path."""

    url: str
    decision: EvidenceDecision
    confidence_score: float
    confidence_reason: str
    failure_reason: EvidenceFailureReason | None = None
    page_type: str = "unknown"
    signals: dict[str, object] = field(default_factory=dict)


def normalize_url(raw_url: str, *, base_url: str | None = None) -> str | None:
    value = (raw_url or "").strip()
    if not value:
        return None
    if base_url:
        value = urljoin(base_url, value)
    if value.startswith("//"):
        value = "https:" + value
    if "://" not in value:
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    path = sub(r"/{2,}", "/", parsed.path or "/")
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.hostname.lower(),
        path=path,
        params="",
        fragment="",
    )
    return urlunparse(normalized)


def host(url: str) -> str:
    return (urlparse(url).hostname or "").strip(".").lower()


def registrable_domain_like(url_or_host: str) -> str:
    """Return a pragmatic base domain without requiring an external PSL dependency.

    This is intentionally conservative and enough for common company hosts such
    as careers.hdi.group and job.hdi.group. It is not used for security-critical
    ownership proof.
    """

    parsed_host = host(url_or_host) if "://" in url_or_host else url_or_host.strip(".").lower()
    parts = [part for part in parsed_host.split(".") if part]
    if len(parts) <= 2:
        return parsed_host
    return ".".join(parts[-2:])


def same_base_domain(url: str, reference_url: str) -> bool:
    return bool(host(url) and registrable_domain_like(url) == registrable_domain_like(reference_url))


def decode_search_redirect_url(raw_url: str, *, base_url: str | None = None) -> str | None:
    normalized = normalize_url(raw_url, base_url=base_url)
    if not normalized:
        return None
    parsed = urlparse(normalized)
    query = parse_qs(parsed.query)
    for key in ("uddg", "url", "u"):
        if key in query and query[key]:
            decoded = normalize_url(unquote(query[key][0]))
            if decoded:
                return decoded
    return normalized


def successfactors_like_job_detail_url(url: str) -> bool:
    parsed = urlparse(url)
    path = sub(r"/{2,}", "/", parsed.path or "").strip("/")
    # Typical shape: /job/Data-&-Analytics-Engineer-%28Long-Tail%29/720-en_US/
    return bool(search(r"(^|/)job/[^/]+/[0-9]+[-_][A-Za-z]{2,}(?:_[A-Z]{2})?/?$", path))


def job_detail_url_shape(url: str) -> bool:
    parsed = urlparse(url)
    path = sub(r"/{2,}", "/", parsed.path.casefold() or "").rstrip("/")
    if not path:
        return False
    if successfactors_like_job_detail_url(url):
        return True
    detail_markers = (
        "/job/",
        "/jobs/",
        "/stellenangebote/",
        "/offene-stellen/",
        "/stellen-finden/",
        "/karriere/jobs/",
        "/karriere/offene-stellen/",
    )
    if not any(marker in f"{path}/" for marker in detail_markers):
        return False
    last = path.rsplit("/", 1)[-1]
    if last in {"job", "jobs", "career", "careers", "karriere", "job_board", "stellenangebote"}:
        return False
    return len(last) >= 6 and ("-" in last or "_" in last or any(char.isdigit() for char in last))


def _candidate_search_hosts(candidate_url: str | None) -> tuple[str, ...]:
    """Return high-value hosts derived from the persisted candidate URL.

    DETAIL-002 deliberately prioritizes the concrete host that already passed
    CAND-001/GATE-001 over generated company-key hosts.  Generated hosts such
    as ``job.e_on_grid_solutions.group`` look plausible in code but waste the
    limited search budget for real portals like ``jobs.eon.com`` and
    ``jobs.hannover-re.com``.
    """

    normalized = normalize_url(candidate_url or "")
    if not normalized:
        return ()
    parsed_host = host(normalized)
    base = registrable_domain_like(normalized)
    candidates = [parsed_host]
    for prefix in ("jobs", "job", "careers", "career"):
        sibling = f"{prefix}.{base}"
        candidates.append(sibling)
    return tuple(item for item in dict.fromkeys(candidates) if item)


def build_search_discovery_queries(
    *,
    company_name: str,
    company_key: str,
    profile_terms: Iterable[str],
    location_terms: Iterable[str],
    max_queries: int = 8,
    candidate_url: str | None = None,
) -> tuple[SearchDiscoveryQuery, ...]:
    company = company_name or company_key
    profile = next((term for term in profile_terms if term), "data")
    location = next((term for term in location_terms if term), "jobs")
    host_queries: list[SearchDiscoveryQuery] = []
    for candidate_host in _candidate_search_hosts(candidate_url):
        host_queries.extend(
            [
                SearchDiscoveryQuery(
                    f"site:{candidate_host}/job {profile} {location}",
                    "persisted candidate host job-detail query",
                ),
                SearchDiscoveryQuery(
                    f"site:{candidate_host} {profile} {location}",
                    "persisted candidate host profile-target query",
                ),
            ]
        )

    queries = [
        *host_queries,
        SearchDiscoveryQuery(f"{company} jobs", "baseline company jobs query"),
        SearchDiscoveryQuery(f"{company} careers", "baseline company careers query"),
        SearchDiscoveryQuery(f"{company} {profile} {location}", "profile and target query"),
        SearchDiscoveryQuery(f"{company_key} jobs", "company key jobs query"),
        SearchDiscoveryQuery(f"site:job.{company_key}.group {profile} {location}", "possible job host site query"),
        SearchDiscoveryQuery(f"site:jobs.{company_key}.group {profile} {location}", "possible jobs host site query"),
        SearchDiscoveryQuery(f"site:careers.{company_key}.group {profile} {location}", "possible careers host site query"),
        SearchDiscoveryQuery(f"site:{company_key}.group/job {profile} {location}", "base-domain job detail query"),
    ]
    unique: list[SearchDiscoveryQuery] = []
    seen: set[str] = set()
    for query in queries:
        if query.query.casefold() in seen:
            continue
        seen.add(query.query.casefold())
        unique.append(query)
    return tuple(unique[:max_queries])


def plausible_sibling_origin_urls(candidate_url: str, *, company_key: str) -> tuple[UrlEvidenceCandidate, ...]:
    normalized = normalize_url(candidate_url)
    if not normalized:
        return ()
    base = registrable_domain_like(normalized)
    original_host = host(normalized)
    host_prefixes = ("careers", "career", "jobs", "job", "karriere")
    paths = ("/", "/jobs", "/job", "/careers", "/karriere/jobs", "/de/karriere/jobs")
    candidates: list[UrlEvidenceCandidate] = [
        UrlEvidenceCandidate(normalized, "candidate_url", 0.90, "persisted candidate URL"),
    ]
    for prefix in host_prefixes:
        sibling_host = f"{prefix}.{base}"
        if sibling_host == original_host:
            continue
        for path in paths:
            candidates.append(
                UrlEvidenceCandidate(
                    f"https://{sibling_host}{path}",
                    "plausible_sibling_host",
                    0.55 if prefix in {"careers", "career"} else 0.65,
                    f"plausible employer-origin sibling host for {company_key}",
                )
            )
    return dedupe_url_candidates(candidates)


def dedupe_url_candidates(candidates: Iterable[UrlEvidenceCandidate]) -> tuple[UrlEvidenceCandidate, ...]:
    result: list[UrlEvidenceCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = normalize_url(candidate.url)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(
            UrlEvidenceCandidate(
                url=normalized,
                discovery_source=candidate.discovery_source,
                confidence_hint=max(0.0, min(1.0, candidate.confidence_hint)),
                reason=candidate.reason,
            )
        )
    return tuple(result)


def classify_checked_url(
    *,
    url: str,
    reference_url: str,
    profile_terms: Iterable[str] = (),
    location_terms: Iterable[str] = (),
    text: str = "",
) -> UrlAssessment:
    if not same_base_domain(url, reference_url):
        return UrlAssessment(
            url=url,
            decision=EvidenceDecision.REJECTED,
            confidence_score=0.88,
            confidence_reason="host does not share the candidate base domain",
            failure_reason=EvidenceFailureReason.DOMAIN_NOT_PLAUSIBLE,
            page_type="external_or_unrelated",
        )

    url_blob = url.casefold()
    text_blob = text.casefold()
    matched_profile = tuple(term for term in profile_terms if term and term.casefold() in f"{url_blob} {text_blob}")
    matched_location = tuple(term for term in location_terms if term and term.casefold() in f"{url_blob} {text_blob}")

    if job_detail_url_shape(url):
        if not text:
            return UrlAssessment(
                url=url,
                decision=EvidenceDecision.IMPLEMENTATION_GAP,
                confidence_score=0.74,
                confidence_reason="URL shape strongly resembles a job detail page but no extracted page text was available",
                failure_reason=EvidenceFailureReason.DETAIL_LINKS_FOUND_BUT_EXTRACTOR_UNSUPPORTED,
                page_type="job_detail_candidate",
                signals={"profile_terms": matched_profile, "location_terms": matched_location},
            )
        if matched_profile and matched_location:
            return UrlAssessment(
                url=url,
                decision=EvidenceDecision.ACCEPTED,
                confidence_score=0.96,
                confidence_reason="job detail URL shape plus extracted profile and target signals",
                failure_reason=EvidenceFailureReason.PROFILE_AND_TARGET_SIGNAL_FOUND,
                page_type="job_detail",
                signals={"profile_terms": matched_profile, "location_terms": matched_location},
            )
        if not matched_profile:
            return UrlAssessment(
                url=url,
                decision=EvidenceDecision.REJECTED,
                confidence_score=0.80,
                confidence_reason="job detail page extracted but no profile signal was found",
                failure_reason=EvidenceFailureReason.DETAIL_PAGE_EXTRACTED_BUT_NO_PROFILE_SIGNAL,
                page_type="job_detail",
                signals={"profile_terms": matched_profile, "location_terms": matched_location},
            )
        return UrlAssessment(
            url=url,
            decision=EvidenceDecision.MANUAL_REVIEW_REQUIRED,
            confidence_score=0.70,
            confidence_reason="job detail page extracted with profile signal but no target/location signal",
            failure_reason=EvidenceFailureReason.DETAIL_PAGE_EXTRACTED_BUT_NO_TARGET_SIGNAL,
            page_type="job_detail",
            signals={"profile_terms": matched_profile, "location_terms": matched_location},
        )

    return UrlAssessment(
        url=url,
        decision=EvidenceDecision.REJECTED,
        confidence_score=0.60,
        confidence_reason="URL is plausible company-domain evidence but does not look like a concrete job detail URL",
        failure_reason=EvidenceFailureReason.GENERIC_CAREER_PAGE_ONLY,
        page_type="listing_or_generic",
        signals={"profile_terms": matched_profile, "location_terms": matched_location},
    )
