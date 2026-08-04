"""Install reviewed employer identity aliases for origin discovery.

The repository already distinguishes legal/display company names from reviewed
corporate identities through ``CORPORATE_IDENTITY_ALIASES``. This contract extends
that existing registry for benchmark-proven market brands and makes the aliases
available to bounded search-query generation.

Aliases are company identity evidence, not URL truth. Every discovered or
operator-supplied URL must still pass normal URL, hostname, origin-type, HTTP,
entity, locale, and side-effect boundaries.
"""

from __future__ import annotations

from dataclasses import replace
import re
from urllib.parse import urlparse

from src.search_intelligence import adaptive_origin_search as adaptive
from src.search_intelligence import origin_quality_contract as quality
import src.search_intelligence.origin_source_discovery_agent as origin_agent

_INSTALL_MARKER = "_origin_registered_identity_contract_installed"
_ORIGINAL_VARIANTS = "_origin_registered_identity_original_brand_surface_variants"
_ORIGINAL_ASSESS = "_origin_registered_identity_original_assess_origin_candidate"
_SHORT_ONLY_REASON = "short-only employer identity is collision-prone and requires review"

REGISTERED_ORIGIN_IDENTITY_ALIASES: dict[str, tuple[str, ...]] = {
    "bridgingit": ("bridging-it", "bridgingit"),
    "compugroup_medical": ("cgm", "compugroup medical"),
    "e_on_digital_technology": (
        "eon",
        "e.on",
        "eon digital technology",
        "e.on digital technology",
    ),
    "ratbacher": ("ratbacher", "ratbacher karriere"),
    "x1f": ("x1f",),
}


def _search_surface(alias: str) -> str:
    raw = str(alias or "").strip().lower()
    if not raw:
        return ""
    if " " in raw:
        return re.sub(r"\s+", " ", raw)
    return raw


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _registered_numeric_host_alias(
    *,
    hostname: str,
    company_key: str,
    company_name: str,
) -> str | None:
    labels = {_compact(label) for label in hostname.split(".") if label}
    for alias in origin_agent.corporate_identity_aliases(company_key, company_name):
        compact = _compact(alias)
        if len(compact) >= 3 and any(ch.isdigit() for ch in compact) and compact in labels:
            return alias
    return None


def install_origin_registered_identity_contract() -> None:
    """Install registry extensions and their bounded runtime uses once."""

    if bool(getattr(origin_agent, _INSTALL_MARKER, False)):
        return

    for company_key, aliases in REGISTERED_ORIGIN_IDENTITY_ALIASES.items():
        existing = origin_agent.CORPORATE_IDENTITY_ALIASES.get(company_key, ())
        origin_agent.CORPORATE_IDENTITY_ALIASES[company_key] = tuple(
            dict.fromkeys((*existing, *aliases))
        )

    # ``jobportal`` is a generic reusable-origin host marker, not a company URL.
    quality.ORIGIN_HOST_LABELS.add("jobportal")

    original_variants = adaptive.brand_surface_variants
    original_assess = origin_agent.assess_origin_candidate
    setattr(adaptive, _ORIGINAL_VARIANTS, original_variants)
    setattr(origin_agent, _ORIGINAL_ASSESS, original_assess)

    def brand_surface_variants_with_registered_aliases(
        *,
        company_name: str,
        company_key: str | None = None,
    ) -> tuple[str, ...]:
        existing = list(
            original_variants(company_name=company_name, company_key=company_key)
        )
        registered = (
            origin_agent.corporate_identity_aliases(company_key, company_name)
            if company_key
            else ()
        )
        ordered: list[str] = []
        if existing:
            ordered.append(existing[0])
        ordered.extend(_search_surface(alias) for alias in registered)
        ordered.extend(existing[1:])
        result: list[str] = []
        for item in ordered:
            if item and item not in result:
                result.append(item)
        return tuple(result[:8])

    def assess_origin_candidate_with_registered_short_brand(
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
        if assessment.decision != "manual_review_candidate":
            return assessment
        if _SHORT_ONLY_REASON not in assessment.reasons:
            return assessment
        blocking_quality_reasons = {
            reason
            for reason in assessment.reasons
            if reason in {
                "job-detail evidence is not a reusable origin source",
                "generic company page lacks a career/job origin locator",
                "short brand/acronym host lacks full employer identity evidence",
                _SHORT_ONLY_REASON,
            }
        }
        if blocking_quality_reasons != {_SHORT_ONLY_REASON}:
            return assessment

        final_url = assessment.final_url or assessment.normalized_url or candidate.url
        hostname = str(urlparse(final_url).hostname or "").lower().strip(".")
        alias = _registered_numeric_host_alias(
            hostname=hostname,
            company_key=company_key,
            company_name=company_name,
        )
        if alias is None:
            return assessment
        return replace(
            assessment,
            decision="select_candidate",
            risk_level="low",
            reasons=tuple(
                (*assessment.reasons, f"exact registered alphanumeric market alias found in host: {alias}")
            ),
        )

    adaptive.brand_surface_variants = brand_surface_variants_with_registered_aliases
    origin_agent.assess_origin_candidate = assess_origin_candidate_with_registered_short_brand
    setattr(origin_agent, _INSTALL_MARKER, True)


__all__ = [
    "REGISTERED_ORIGIN_IDENTITY_ALIASES",
    "install_origin_registered_identity_contract",
]
