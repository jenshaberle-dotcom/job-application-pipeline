"""Canonical deterministic ATS provider recognition for LLM-BOOST-001.

Provider recognition is deliberately weaker than employer/tenant authority.
This module performs no network, provider, database, connector activation, or
product mutation.  It only classifies already-observed host/text evidence and
returns the deterministic next authority step.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable
from urllib.parse import urlparse


ATS_PROVIDER_REGISTRY_VERSION = "LLM-BOOST-001.ats-provider-registry.v1"


@dataclass(frozen=True)
class ATSProviderDefinition:
    provider: str
    confidence: float
    host_suffixes: tuple[str, ...]
    text_patterns: tuple[str, ...]
    authority_next_action: str = "provider_specific_deterministic_probe"
    family: str = "ats"


@dataclass(frozen=True)
class ATSProviderRecognition:
    contract_version: str
    provider: str
    family: str
    confidence: float
    host: str
    matched_host_suffix: str
    target_hint: str | None
    next_action: str
    provider_recognized: bool = True
    tenant_authority: bool = False
    delegation_permitted: bool = False
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "provider": self.provider,
            "family": self.family,
            "confidence": self.confidence,
            "host": self.host,
            "matched_host_suffix": self.matched_host_suffix,
            "target_hint": self.target_hint,
            "next_action": self.next_action,
            "provider_recognized": self.provider_recognized,
            "tenant_authority": self.tenant_authority,
            "delegation_permitted": self.delegation_permitted,
            "product_authority": self.product_authority,
        }


ATS_PROVIDER_DEFINITIONS: tuple[ATSProviderDefinition, ...] = (
    ATSProviderDefinition(
        "greenhouse",
        0.98,
        ("greenhouse.io",),
        (r"greenhouse\.io", r"boards\.greenhouse\.io"),
        "validate_greenhouse_board_authority",
    ),
    ATSProviderDefinition(
        "personio",
        0.98,
        ("personio.de", "personio.com"),
        (r"personio\.(?:de|com)", r"jobs\.personio\."),
        "validate_personio_target_authority",
    ),
    ATSProviderDefinition(
        "workday",
        0.96,
        ("myworkdayjobs.com", "workdayjobs.com"),
        (r"myworkdayjobs\.com", r"workdayjobs\.com"),
    ),
    ATSProviderDefinition(
        "successfactors",
        0.96,
        ("successfactors.com", "successfactors.eu", "sapsf.com"),
        (r"successfactors\.(?:com|eu)", r"sapsf\."),
        "validate_successfactors_tenant_authority",
    ),
    ATSProviderDefinition(
        "smartrecruiters",
        0.96,
        ("smartrecruiters.com",),
        (r"smartrecruiters\.com",),
    ),
    ATSProviderDefinition("lever", 0.96, ("lever.co",), (r"lever\.co", r"jobs\.lever\.co")),
    ATSProviderDefinition(
        "ashby",
        0.96,
        ("ashbyhq.com",),
        (r"ashbyhq\.com", r"jobs\.ashbyhq\.com"),
    ),
    ATSProviderDefinition(
        "recruitee",
        0.94,
        ("recruitee.com", "recruitee.io"),
        (r"recruitee\.com", r"recruitee\.io"),
    ),
    ATSProviderDefinition(
        "workable",
        0.94,
        ("workable.com",),
        (r"workable\.com", r"apply\.workable\.com"),
    ),
    ATSProviderDefinition(
        "softgarden",
        0.94,
        ("softgarden.de", "softgarden.io"),
        (r"softgarden\.(?:de|io)",),
    ),
    ATSProviderDefinition(
        "dvinci",
        0.94,
        ("dvinci.de", "dvinci.com", "dvinci-hr.com"),
        (r"dvinci\.(?:de|com)", r"dvinci-hr\.com"),
    ),
    ATSProviderDefinition(
        "onlyfy",
        0.92,
        ("onlyfy.io", "prescreen.io"),
        (r"onlyfy\.io", r"prescreen\.io"),
    ),
    ATSProviderDefinition("join", 0.90, ("join.com",), (r"join\.com", r"join\.com/companies")),
    ATSProviderDefinition("talention", 0.90, ("talention.com",), (r"talention\.com",)),
    ATSProviderDefinition(
        "umantis",
        0.90,
        ("umantis.com",),
        (r"umantis\.com", r"haufe-umantis"),
    ),
    ATSProviderDefinition(
        "icims",
        0.90,
        ("icims.com",),
        (r"icims\.com", r"careers-.*\.icims\.com"),
    ),
    ATSProviderDefinition(
        "oracle",
        0.88,
        ("oraclecloud.com",),
        (r"oraclecloud\.com", r"fa-ext\.oraclecloud\.com"),
    ),
    ATSProviderDefinition("breezy", 0.88, ("breezy.hr",), (r"breezy\.hr",)),
    ATSProviderDefinition("comeet", 0.88, ("comeet.com",), (r"comeet\.com",)),
    ATSProviderDefinition("jobbase", 0.86, ("jobbase.io",), (r"jobbase\.io",)),
)


def _normalized_host(url_or_host: str) -> str:
    value = (url_or_host or "").strip().lower()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"//{value}")
    return (parsed.hostname or "").rstrip(".")


def _matches_suffix(host: str, suffix: str) -> bool:
    suffix = suffix.lower().rstrip(".")
    return bool(host and (host == suffix or host.endswith(f".{suffix}")))


def _personio_target_hint(host: str, suffix: str) -> str | None:
    marker = f".jobs.{suffix}"
    if host.endswith(marker):
        target = host[: -len(marker)].split(".")[-1]
        if re.fullmatch(r"[a-z0-9-]+", target):
            return target
    return None


def _target_hint(provider: str, host: str, suffix: str) -> str | None:
    if provider == "personio":
        return _personio_target_hint(host, suffix)
    return None


def recognize_ats_provider(url_or_host: str) -> ATSProviderRecognition | None:
    """Recognize an ATS host without granting employer/tenant authority."""

    host = _normalized_host(url_or_host)
    if not host:
        return None
    for definition in ATS_PROVIDER_DEFINITIONS:
        for suffix in definition.host_suffixes:
            if not _matches_suffix(host, suffix):
                continue
            return ATSProviderRecognition(
                contract_version=ATS_PROVIDER_REGISTRY_VERSION,
                provider=definition.provider,
                family=definition.family,
                confidence=definition.confidence,
                host=host,
                matched_host_suffix=suffix,
                target_hint=_target_hint(definition.provider, host, suffix),
                next_action=definition.authority_next_action,
            )
    return None


def is_known_ats_host(url_or_host: str) -> bool:
    return recognize_ats_provider(url_or_host) is not None


def trusted_ats_host_suffixes() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                suffix
                for definition in ATS_PROVIDER_DEFINITIONS
                for suffix in definition.host_suffixes
            }
        )
    )


def provider_pattern_dicts() -> tuple[dict[str, object], ...]:
    """Compatibility projection for read-only provider-evidence discovery."""

    return tuple(
        {
            "provider": definition.provider,
            "family": definition.family,
            "confidence": definition.confidence,
            "patterns": definition.text_patterns,
        }
        for definition in ATS_PROVIDER_DEFINITIONS
    )


def classify_provider_names(text: str) -> tuple[str, ...]:
    """Return deterministic provider names found in arbitrary evidence text."""

    haystack = (text or "").lower()
    found: set[str] = set()
    for definition in ATS_PROVIDER_DEFINITIONS:
        if any(re.search(pattern, haystack, re.IGNORECASE) for pattern in definition.text_patterns):
            found.add(definition.provider)
    return tuple(sorted(found))


__all__ = [
    "ATS_PROVIDER_DEFINITIONS",
    "ATS_PROVIDER_REGISTRY_VERSION",
    "ATSProviderDefinition",
    "ATSProviderRecognition",
    "classify_provider_names",
    "is_known_ats_host",
    "provider_pattern_dicts",
    "recognize_ats_provider",
    "trusted_ats_host_suffixes",
]
