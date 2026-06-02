"""Origin source discovery gate for employer-origin candidates.

This module deliberately does not browse the web. It evaluates already persisted
URL evidence and decides whether the origin-source URL is safe and concrete
enough to continue toward connector feasibility and build planning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import ip_address
from re import sub
from typing import Any
from urllib.parse import urlparse, urlunparse

SAFE_SOURCE_TYPES = {
    "employer_origin_career_site",
    "employer_origin_ats_backed_career_site",
}
KNOWN_AGGREGATOR_DOMAINS = (
    "stepstone.de",
    "linkedin.com",
    "indeed.com",
    "xing.com",
    "glassdoor.de",
    "monster.de",
    "jobware.de",
    "stellenanzeigen.de",
)
CAREER_PATH_MARKERS = (
    "career",
    "careers",
    "karriere",
    "jobs",
    "stellen",
    "stellenangebote",
    "jobboerse",
    "jobbörse",
    "recruiting",
    "bewerbung",
    "join-us",
    "work-with-us",
)
UNSAFE_SCHEMES = {"", "file", "javascript", "data", "ftp", "mailto"}


@dataclass(frozen=True)
class CandidateUrlEvidence:
    """Persisted URL evidence for one employer-origin candidate."""

    url: str
    evidence_source: str
    source_priority: int = 50
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceUrlAssessment:
    """Safety and usefulness assessment for one URL."""

    input_url: str
    normalized_url: str | None
    domain: str | None
    source_type: str
    safe_to_probe_later: bool
    confidence_score: float
    risk_level: str
    decision: str
    reasons: tuple[str, ...]
    evidence_source: str
    source_priority: int


@dataclass(frozen=True)
class OriginSourceDiscoveryDecision:
    """Gate decision for one candidate."""

    company_key: str
    company_name: str
    discovery_status: str
    decision: str
    selected_origin_url: str | None
    selected_domain: str | None
    selected_source_type: str | None
    confidence_score: float
    risk_level: str
    blocker_code: str | None
    reason: str
    alternatives: tuple[SourceUrlAssessment, ...]
    rejected_urls: tuple[SourceUrlAssessment, ...]
    boundary: tuple[str, ...] = (
        "no web browsing",
        "no connector registration",
        "no source activation",
        "no Bronze write",
        "no scheduler change",
    )


def normalize_url(raw_url: str) -> str | None:
    """Return a stable HTTPS/HTTP URL representation or None for invalid input."""

    candidate = (raw_url or "").strip()
    if not candidate:
        return None
    # Reject explicit unsafe schemes before adding a default scheme.
    # Without this guard, values such as javascript:alert(1) could be
    # misread as a hostname after prefixing https://.
    scheme_probe = urlparse(candidate)
    if scheme_probe.scheme and scheme_probe.scheme.lower() in UNSAFE_SCHEMES:
        return None
    if scheme_probe.scheme and scheme_probe.scheme.lower() not in {"http", "https"}:
        return None
    if "://" not in candidate:
        candidate = "https://" + candidate
    parsed = urlparse(candidate)
    if parsed.scheme.lower() in UNSAFE_SCHEMES or not parsed.netloc:
        return None
    hostname = (parsed.hostname or "").strip(".").lower()
    if not hostname:
        return None
    path = sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=hostname,
        path=path,
        params="",
        query="",
        fragment="",
    )
    return urlunparse(normalized)


def is_public_domain(hostname: str | None) -> bool:
    """Reject localhost, private IPs and hostnames without a public-looking dot."""

    if not hostname:
        return False
    host = hostname.strip(".").lower()
    if host in {"localhost", "0.0.0.0"}:
        return False
    try:
        address = ip_address(host)
    except ValueError:
        return "." in host and " " not in host
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
    )


def is_known_aggregator_domain(hostname: str | None) -> bool:
    """Return true for known job aggregators that must not become origin sources."""

    if not hostname:
        return False
    host = hostname.strip(".").lower()
    return any(host == domain or host.endswith("." + domain) for domain in KNOWN_AGGREGATOR_DOMAINS)


def classify_source_type(url: str) -> tuple[str, float, tuple[str, ...]]:
    """Classify URL concreteness without fetching the page."""

    parsed = urlparse(url)
    path = (parsed.path or "/").lower()
    reasons: list[str] = []
    if any(marker in path for marker in CAREER_PATH_MARKERS):
        reasons.append("career-like path marker found")
        return "employer_origin_career_site", 0.80, tuple(reasons)
    if parsed.path in ("", "/"):
        reasons.append("homepage only; origin page must be confirmed")
        return "unknown_company_homepage", 0.45, tuple(reasons)
    reasons.append("non-career path; manual verification recommended")
    return "unknown_candidate_page", 0.55, tuple(reasons)


def assess_url(evidence: CandidateUrlEvidence) -> SourceUrlAssessment:
    """Assess one persisted URL evidence item."""

    normalized = normalize_url(evidence.url)
    if normalized is None:
        return SourceUrlAssessment(
            input_url=evidence.url,
            normalized_url=None,
            domain=None,
            source_type="invalid_url",
            safe_to_probe_later=False,
            confidence_score=0.0,
            risk_level="blocked",
            decision="reject",
            reasons=("invalid or unsupported URL",),
            evidence_source=evidence.evidence_source,
            source_priority=evidence.source_priority,
        )
    parsed = urlparse(normalized)
    reasons: list[str] = []
    if parsed.scheme != "https":
        reasons.append("HTTPS is required before later probing")
        return SourceUrlAssessment(
            input_url=evidence.url,
            normalized_url=normalized,
            domain=parsed.hostname,
            source_type="unsafe_non_https_url",
            safe_to_probe_later=False,
            confidence_score=0.20,
            risk_level="high",
            decision="reject",
            reasons=tuple(reasons),
            evidence_source=evidence.evidence_source,
            source_priority=evidence.source_priority,
        )
    if not is_public_domain(parsed.hostname):
        reasons.append("host is not public-domain evidence")
        return SourceUrlAssessment(
            input_url=evidence.url,
            normalized_url=normalized,
            domain=parsed.hostname,
            source_type="unsafe_private_or_local_host",
            safe_to_probe_later=False,
            confidence_score=0.10,
            risk_level="blocked",
            decision="reject",
            reasons=tuple(reasons),
            evidence_source=evidence.evidence_source,
            source_priority=evidence.source_priority,
        )
    if is_known_aggregator_domain(parsed.hostname):
        reasons.append("known aggregator domain; usable as market evidence only")
        return SourceUrlAssessment(
            input_url=evidence.url,
            normalized_url=normalized,
            domain=parsed.hostname,
            source_type="aggregator_job_board_evidence",
            safe_to_probe_later=False,
            confidence_score=0.0,
            risk_level="medium",
            decision="reject",
            reasons=tuple(reasons),
            evidence_source=evidence.evidence_source,
            source_priority=evidence.source_priority,
        )
    source_type, confidence, type_reasons = classify_source_type(normalized)
    reasons.extend(type_reasons)
    safe = source_type in SAFE_SOURCE_TYPES
    return SourceUrlAssessment(
        input_url=evidence.url,
        normalized_url=normalized,
        domain=parsed.hostname,
        source_type=source_type,
        safe_to_probe_later=True,
        confidence_score=confidence,
        risk_level="low" if safe else "medium",
        decision="candidate" if safe else "manual_review_required",
        reasons=tuple(reasons),
        evidence_source=evidence.evidence_source,
        source_priority=evidence.source_priority,
    )


def decide_origin_source(
    *,
    company_key: str,
    company_name: str,
    url_evidence: list[CandidateUrlEvidence],
) -> OriginSourceDiscoveryDecision:
    """Select or reject origin-source URL evidence for a candidate."""

    assessments_by_url: dict[str, SourceUrlAssessment] = {}
    for item in url_evidence:
        assessed = assess_url(item)
        dedupe_key = assessed.normalized_url or item.url
        existing = assessments_by_url.get(dedupe_key)
        if existing is None or item.source_priority < existing.source_priority:
            assessments_by_url[dedupe_key] = assessed

    assessments = sorted(
        assessments_by_url.values(),
        key=lambda item: (item.decision != "candidate", -item.confidence_score, item.source_priority),
    )
    usable = [item for item in assessments if item.decision == "candidate" and item.normalized_url]
    rejected = [item for item in assessments if item.decision == "reject"]
    review = [item for item in assessments if item.decision == "manual_review_required"]

    if not assessments:
        return OriginSourceDiscoveryDecision(
            company_key=company_key,
            company_name=company_name,
            discovery_status="not_found",
            decision="manual_review_required",
            selected_origin_url=None,
            selected_domain=None,
            selected_source_type=None,
            confidence_score=0.0,
            risk_level="unknown",
            blocker_code="no_origin_url_evidence",
            reason="No persisted origin URL evidence is available for this candidate.",
            alternatives=(),
            rejected_urls=(),
        )

    if usable:
        selected = usable[0]
        domains = {item.domain for item in usable if item.domain}
        if len(domains) > 1 and usable[0].confidence_score < 0.90:
            return OriginSourceDiscoveryDecision(
                company_key=company_key,
                company_name=company_name,
                discovery_status="manual_review_required",
                decision="manual_review_required",
                selected_origin_url=None,
                selected_domain=None,
                selected_source_type=None,
                confidence_score=usable[0].confidence_score,
                risk_level="medium",
                blocker_code="ambiguous_multiple_origin_domains",
                reason="Multiple plausible HTTPS origin domains were found; manual review must choose one before connector feasibility.",
                alternatives=tuple(usable + review),
                rejected_urls=tuple(rejected),
            )
        return OriginSourceDiscoveryDecision(
            company_key=company_key,
            company_name=company_name,
            discovery_status="selected",
            decision="continue_to_connector_feasibility",
            selected_origin_url=selected.normalized_url,
            selected_domain=selected.domain,
            selected_source_type=selected.source_type,
            confidence_score=selected.confidence_score,
            risk_level=selected.risk_level,
            blocker_code=None,
            reason="A public HTTPS career-like origin URL was selected from persisted evidence.",
            alternatives=tuple(assessments),
            rejected_urls=tuple(rejected),
        )

    if rejected and not review:
        blocking_rejections = [
            item
            for item in rejected
            if item.source_type != "aggregator_job_board_evidence"
        ]
        if not blocking_rejections:
            return OriginSourceDiscoveryDecision(
                company_key=company_key,
                company_name=company_name,
                discovery_status="not_found",
                decision="manual_review_required",
                selected_origin_url=None,
                selected_domain=None,
                selected_source_type=None,
                confidence_score=0.0,
                risk_level="unknown",
                blocker_code="market_evidence_without_origin_url",
                reason=(
                    "Only aggregator or market-evidence URLs were found. "
                    "No persisted employer-origin URL evidence is available yet."
                ),
                alternatives=(),
                rejected_urls=tuple(rejected),
            )
        return OriginSourceDiscoveryDecision(
            company_key=company_key,
            company_name=company_name,
            discovery_status="blocked_unsafe_url",
            decision="abort_documented",
            selected_origin_url=None,
            selected_domain=None,
            selected_source_type=None,
            confidence_score=0.0,
            risk_level="blocked",
            blocker_code="only_unsafe_origin_url_evidence",
            reason="Only invalid, non-HTTPS, local or private URL evidence was found.",
            alternatives=(),
            rejected_urls=tuple(rejected),
        )

    return OriginSourceDiscoveryDecision(
        company_key=company_key,
        company_name=company_name,
        discovery_status="manual_review_required",
        decision="manual_review_required",
        selected_origin_url=None,
        selected_domain=None,
        selected_source_type=None,
        confidence_score=max((item.confidence_score for item in review), default=0.0),
        risk_level="medium",
        blocker_code="origin_url_not_concrete_enough",
        reason="Only homepage or non-career URL evidence was found; manual review must confirm the origin page.",
        alternatives=tuple(review),
        rejected_urls=tuple(rejected),
    )


def assessment_to_json(assessment: SourceUrlAssessment) -> dict[str, Any]:
    return {
        "input_url": assessment.input_url,
        "normalized_url": assessment.normalized_url,
        "domain": assessment.domain,
        "source_type": assessment.source_type,
        "safe_to_probe_later": assessment.safe_to_probe_later,
        "confidence_score": assessment.confidence_score,
        "risk_level": assessment.risk_level,
        "decision": assessment.decision,
        "reasons": list(assessment.reasons),
        "evidence_source": assessment.evidence_source,
        "source_priority": assessment.source_priority,
    }


def decision_to_json(decision: OriginSourceDiscoveryDecision) -> dict[str, Any]:
    return {
        "company_key": decision.company_key,
        "company_name": decision.company_name,
        "discovery_status": decision.discovery_status,
        "decision": decision.decision,
        "selected_origin_url": decision.selected_origin_url,
        "selected_domain": decision.selected_domain,
        "selected_source_type": decision.selected_source_type,
        "confidence_score": decision.confidence_score,
        "risk_level": decision.risk_level,
        "blocker_code": decision.blocker_code,
        "reason": decision.reason,
        "alternatives": [assessment_to_json(item) for item in decision.alternatives],
        "rejected_urls": [assessment_to_json(item) for item in decision.rejected_urls],
        "boundary": list(decision.boundary),
    }
