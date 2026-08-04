"""Validate challenge-blocked operator URLs through publisher-owned sitemap evidence.

An explicit operator URL remains untrusted and first passes the normal deterministic
assessment. A generic HTTP 403 is never accepted. Only an operator-supplied URL
that reached a narrow anti-bot challenge state may receive one additional,
same-origin ``/sitemap.xml`` read.

Selection is possible only when all normal identity and origin-quality scores are
already sufficient, the URL path anchors a distinctive employer entity token,
and the publisher sitemap declares the exact normalized operator URL. Generated
or provider-discovered URLs are never eligible.

The contract adds no search-provider or LLM call and performs no database or
pipeline mutation.
"""

from __future__ import annotations

from dataclasses import replace
import re
from typing import Callable
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests

from src.search_intelligence import origin_quality_contract as quality
import src.search_intelligence.origin_source_discovery_agent as origin_agent

_INSTALL_MARKER = "_origin_operator_sitemap_evidence_contract_installed"
_ORIGINAL_ASSESS = "_origin_operator_sitemap_evidence_original_assess"
_OPERATOR_PROVIDER = "operator_supplied_unvalidated"
_CHALLENGE_STATUS = 403
_CHALLENGE_TITLE = "justamoment"
_MAX_CHALLENGE_BYTES = 100_000
_MAX_SITEMAP_BYTES = 10_000_000
_SITEMAP_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "X-Automation-Client": "job-application-pipeline-origin-source-discovery/0.1",
}
_HARD_BLOCKING_REASONS = {
    "company identity match too weak",
    "job-detail evidence is not a reusable origin source",
    "generic company page lacks a career/job origin locator",
}


def _compact(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", origin_agent.ascii_fold(value))


def _distinctive_company_tokens(company_name: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in origin_agent.tokenize(company_name)
        if len(token) >= 5
        and token not in origin_agent.LEGAL_OR_GENERIC_TOKENS
        and token not in origin_agent.LOCALITY_TOKENS
        and token not in {"and", "und", "the", "der", "die", "das"}
    )


def _path_anchors_company_entity(url: str, company_name: str) -> bool:
    path = _compact(urlparse(url).path)
    return bool(path) and any(
        token in path for token in _distinctive_company_tokens(company_name)
    )


def _is_exact_challenge_state(
    assessment: origin_agent.OriginDiscoveryAssessment,
) -> bool:
    probe = assessment.probe
    if probe is None:
        return False
    if probe.status_code != _CHALLENGE_STATUS or probe.reachable:
        return False
    if _compact(probe.title) != _CHALLENGE_TITLE:
        return False
    if probe.response_bytes <= 0 or probe.response_bytes > _MAX_CHALLENGE_BYTES:
        return False

    normalized = origin_agent.normalize_candidate_url(assessment.normalized_url)
    final_url = origin_agent.normalize_candidate_url(probe.final_url)
    return normalized is not None and final_url == normalized


def _response_content(response: object) -> bytes:
    raw = getattr(response, "content", b"") or b""
    if isinstance(raw, bytes):
        return raw
    return str(raw).encode("utf-8", errors="replace")


def _same_origin_sitemap_declares_exact_url(
    target_url: str,
    *,
    timeout_seconds: float,
) -> tuple[bool, str]:
    normalized_target = origin_agent.normalize_candidate_url(target_url)
    if normalized_target is None:
        return False, "invalid normalized operator URL"

    parsed = urlparse(normalized_target)
    if parsed.scheme != "https" or not parsed.hostname:
        return False, "operator URL is not an HTTPS origin"

    sitemap_url = f"https://{parsed.hostname}/sitemap.xml"
    try:
        response = requests.get(
            sitemap_url,
            timeout=timeout_seconds,
            headers=dict(_SITEMAP_HEADERS),
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        return False, f"same-origin sitemap request failed: {exc.__class__.__name__}"

    status_code = int(getattr(response, "status_code", 0) or 0)
    if status_code not in origin_agent.HTTP_ACCEPTED_STATUS_CODES:
        return False, f"same-origin sitemap rejected: status={status_code}"

    final_sitemap_url = str(getattr(response, "url", "") or sitemap_url)
    final_host = str(urlparse(final_sitemap_url).hostname or "").lower().strip(".")
    if final_host != parsed.hostname.lower().strip("."):
        return False, "sitemap redirect left the operator origin"

    content = _response_content(response)
    if not content:
        return False, "same-origin sitemap response was empty"
    if len(content) > _MAX_SITEMAP_BYTES:
        return False, "same-origin sitemap exceeded the bounded size limit"

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return False, "same-origin sitemap was not valid XML"

    declared_urls = {
        normalized
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "loc" and element.text
        if (normalized := origin_agent.normalize_candidate_url(element.text))
        is not None
    }
    if normalized_target not in declared_urls:
        return False, "same-origin sitemap did not declare the exact operator URL"
    return True, "exact operator URL declared by same-origin publisher sitemap"


def assess_with_operator_sitemap_evidence(
    original_assess: Callable[..., origin_agent.OriginDiscoveryAssessment],
    candidate: origin_agent.OriginDiscoveryCandidate,
    *,
    company_key: str,
    company_name: str,
    source_family_candidate: str | None = None,
    probe=None,
    timeout_seconds: float = 8.0,
) -> origin_agent.OriginDiscoveryAssessment:
    """Promote only an exact, publisher-declared challenge-blocked operator URL."""

    assessment = original_assess(
        candidate,
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family_candidate,
        probe=probe,
    )
    if assessment.decision != "reject":
        return assessment
    if candidate.provider != _OPERATOR_PROVIDER:
        return assessment
    if not _is_exact_challenge_state(assessment):
        return assessment
    if assessment.identity_score < 0.45:
        return assessment
    if assessment.total_score < origin_agent.AUTO_SELECT_MIN_SCORE:
        return assessment
    if any(reason in _HARD_BLOCKING_REASONS for reason in assessment.reasons):
        return assessment

    target_url = assessment.normalized_url or candidate.url
    if quality.is_job_detail_url(target_url) or not quality._has_origin_locator(target_url):
        return assessment
    if not _path_anchors_company_entity(target_url, company_name):
        return assessment

    declared, evidence = _same_origin_sitemap_declares_exact_url(
        target_url,
        timeout_seconds=timeout_seconds,
    )
    if not declared:
        return replace(
            assessment,
            reasons=tuple((*assessment.reasons, evidence)),
        )

    return replace(
        assessment,
        decision="select_candidate",
        risk_level="low",
        reasons=tuple((*assessment.reasons, evidence)),
    )


def install_origin_operator_sitemap_evidence_contract() -> None:
    """Install the exact publisher-sitemap evidence wrapper once."""

    if bool(getattr(origin_agent, _INSTALL_MARKER, False)):
        return

    original_assess = origin_agent.assess_origin_candidate
    setattr(origin_agent, _ORIGINAL_ASSESS, original_assess)

    def assess_with_publisher_sitemap(
        candidate: origin_agent.OriginDiscoveryCandidate,
        *,
        company_key: str,
        company_name: str,
        source_family_candidate: str | None = None,
        probe=None,
    ) -> origin_agent.OriginDiscoveryAssessment:
        return assess_with_operator_sitemap_evidence(
            original_assess,
            candidate,
            company_key=company_key,
            company_name=company_name,
            source_family_candidate=source_family_candidate,
            probe=probe,
        )

    origin_agent.assess_origin_candidate = assess_with_publisher_sitemap
    setattr(origin_agent, _INSTALL_MARKER, True)


__all__ = [
    "assess_with_operator_sitemap_evidence",
    "install_origin_operator_sitemap_evidence_contract",
]
