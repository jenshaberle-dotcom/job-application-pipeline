"""Resolve live short-alias false reviews with bounded identity evidence.

The reviewed alias registry may contain short market brands such as ``CGM`` or
``EON``. A prior safety wrapper deliberately downgraded short pure-letter hosts
when the probed page title did not repeat the long legal employer name. Real
career pages may expose generic or client-rendered titles, so this outer contract
accepts two stronger alternatives while preserving the TIB/IVV collision guards:

- an explicitly audited exact-host identity alias;
- a registered short host alias plus a distinctive employer token in the origin
  path.

Only candidates already selected by all normal origin gates and then downgraded
by the short-alias title/path guard are eligible. No URL is allowlisted.
"""

from __future__ import annotations

from dataclasses import replace
import re
from urllib.parse import urlparse

import src.search_intelligence.origin_source_discovery_agent as origin_agent

_INSTALL_MARKER = "_origin_registered_short_alias_live_evidence_installed"
_ORIGINAL_ASSESS = "_origin_registered_short_alias_live_evidence_original_assess"
_SHORT_ALIAS_GUARD_REASON = (
    "short registered alias host lacks full employer identity in probed page title or origin path"
)

REGISTERED_EXACT_HOST_IDENTITY_ALIASES: dict[str, tuple[str, ...]] = {
    "compugroup_medical": ("cgm",),
}


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _matching_short_host_alias(
    *,
    hostname: str,
    company_key: str,
    company_name: str,
) -> str | None:
    labels = {_compact(label) for label in hostname.split(".") if label}
    for alias in origin_agent.corporate_identity_aliases(company_key, company_name):
        compact = _compact(alias)
        if compact.isalpha() and 3 <= len(compact) <= 4 and compact in labels:
            return alias
    return None


def _is_audited_exact_host_identity(
    *,
    company_key: str,
    alias: str,
) -> bool:
    compact = _compact(alias)
    return compact in {
        _compact(item)
        for item in REGISTERED_EXACT_HOST_IDENTITY_ALIASES.get(company_key, ())
    }


def _distinctive_company_tokens(company_name: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in origin_agent.tokenize(company_name)
        if len(token) >= 5
        and token not in origin_agent.LEGAL_OR_GENERIC_TOKENS
        and token not in origin_agent.LOCALITY_TOKENS
        and token not in {"and", "und", "the", "der", "die", "das"}
    )


def _path_anchors_company_entity(final_url: str, company_name: str) -> bool:
    path = _compact(urlparse(final_url).path)
    return bool(path) and any(
        token in path for token in _distinctive_company_tokens(company_name)
    )


def install_origin_registered_short_alias_live_evidence_contract() -> None:
    """Install the bounded live-evidence promotion wrapper once."""

    if bool(getattr(origin_agent, _INSTALL_MARKER, False)):
        return

    original_assess = origin_agent.assess_origin_candidate
    setattr(origin_agent, _ORIGINAL_ASSESS, original_assess)

    def assess_with_registered_short_alias_live_evidence(
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
        if _SHORT_ALIAS_GUARD_REASON not in assessment.reasons:
            return assessment

        final_url = assessment.final_url or assessment.normalized_url or candidate.url
        hostname = str(urlparse(final_url).hostname or "").lower().strip(".")
        alias = _matching_short_host_alias(
            hostname=hostname,
            company_key=company_key,
            company_name=company_name,
        )
        if alias is None:
            return assessment

        exact_identity = _is_audited_exact_host_identity(
            company_key=company_key,
            alias=alias,
        )
        path_identity = _path_anchors_company_entity(final_url, company_name)
        if not exact_identity and not path_identity:
            return assessment

        evidence = (
            "audited exact-host identity alias"
            if exact_identity
            else "distinctive employer entity token found in origin path"
        )
        return replace(
            assessment,
            decision="select_candidate",
            risk_level="low",
            reasons=tuple(
                (*assessment.reasons, f"registered short alias accepted with {evidence}: {alias}")
            ),
        )

    origin_agent.assess_origin_candidate = assess_with_registered_short_alias_live_evidence
    setattr(origin_agent, _INSTALL_MARKER, True)


__all__ = [
    "REGISTERED_EXACT_HOST_IDENTITY_ALIASES",
    "install_origin_registered_short_alias_live_evidence_contract",
]
