"""Require host-bound employer identity for automatic origin selection.

A third-party guide or profile can place the full employer name in its URL path,
page title, and snippet. Those signals are useful evidence, but they do not make
the third-party host an employer origin source. Automatic selection therefore
requires either:

- employer/source-family identity in the hostname; or
- a known tenant-capable ATS hostname whose tenant path is validated separately.

The contract is installed after the existing origin-quality contract and only
narrows ``select_candidate`` decisions. It does not lower any score or authorize
persistence.
"""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import urlparse

import src.search_intelligence.origin_source_discovery as origin_discovery
import src.search_intelligence.origin_source_discovery_agent as origin_agent

_INSTALL_MARKER = "_origin_host_identity_contract_installed"
_ORIGINAL_ASSESS = "_origin_host_identity_original_assess_origin_candidate"

# Taxonomy consistency: these domains can provide market/search evidence, but
# they are not employer-owned origin sources. Shared ATS domains are deliberately
# excluded because a concrete tenant URL may be a valid origin source.
THIRD_PARTY_ORIGIN_DOMAINS = (
    "eujobs.co",
    "levels.fyi",
    "get-in-it.de",
    "connecticum.de",
    "kununu.com",
    "glassdoor.com",
    "glassdoor.de",
    "reveliolabs.com",
    "leading-employers.org",
    "arbeitnow.com",
    "datacareer.de",
    "talent.com",
    "jooble.org",
    "adzuna.de",
    "simplyhired.de",
    "studysmarter.de",
    "devjobs.de",
    "kimeta.de",
    "finest-jobs.com",
    "bankjob.de",
    "karriere.at",
    "nofluffjobs.com",
    "owcareers.com",
    "seat11a.com",
)


def _host_identity_score(
    *,
    hostname: str,
    company_key: str,
    company_name: str,
    source_family_candidate: str | None,
) -> float:
    score, _ = origin_agent.company_identity_score(
        url=f"https://{hostname}/",
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family_candidate,
    )
    return float(score)


def install_origin_host_identity_contract() -> None:
    """Install host-bound identity and third-party taxonomy exactly once."""

    if bool(getattr(origin_agent, _INSTALL_MARKER, False)):
        return

    origin_discovery.KNOWN_AGGREGATOR_DOMAINS = tuple(
        dict.fromkeys(
            (
                *origin_discovery.KNOWN_AGGREGATOR_DOMAINS,
                *THIRD_PARTY_ORIGIN_DOMAINS,
            )
        )
    )

    original_assess = origin_agent.assess_origin_candidate
    setattr(origin_agent, _ORIGINAL_ASSESS, original_assess)

    def assess_origin_candidate_with_host_identity(
        candidate: origin_agent.OriginDiscoveryCandidate,
        *,
        company_key: str,
        company_name: str,
        source_family_candidate: str | None = None,
        probe=None,
    ) -> origin_agent.OriginDiscoveryAssessment:
        assessment = original_assess(
            candidate,
            company_key=company_key,
            company_name=company_name,
            source_family_candidate=source_family_candidate,
            probe=probe,
        )
        if assessment.decision != "select_candidate":
            return assessment

        final_url = assessment.final_url or assessment.normalized_url or candidate.url
        hostname = str(urlparse(final_url).hostname or "").lower().strip(".")
        if not hostname:
            return replace(
                assessment,
                decision="reject",
                risk_level="blocked",
                reasons=tuple((*assessment.reasons, "origin hostname is missing")),
            )

        if origin_agent.is_known_ats_provider_domain(hostname):
            return assessment

        host_identity = _host_identity_score(
            hostname=hostname,
            company_key=company_key,
            company_name=company_name,
            source_family_candidate=source_family_candidate,
        )
        if host_identity >= 0.45:
            return assessment

        return replace(
            assessment,
            decision="reject",
            risk_level="medium",
            reasons=tuple(
                (
                    *assessment.reasons,
                    "employer identity appears only in path/search context; origin host is not employer-bound",
                )
            ),
        )

    origin_agent.assess_origin_candidate = assess_origin_candidate_with_host_identity
    setattr(origin_agent, _INSTALL_MARKER, True)


__all__ = [
    "THIRD_PARTY_ORIGIN_DOMAINS",
    "install_origin_host_identity_contract",
]
