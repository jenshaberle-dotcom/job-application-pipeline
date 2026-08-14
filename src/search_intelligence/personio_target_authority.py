"""Deterministic Personio target/employer authority validation for LLM-BOOST-001.

This module consumes already-bounded public Personio XML evidence.  It performs
no HTTP request, provider call, database access, activation, or product write.
A Personio hostname/target hint is only routing evidence; authority additionally
requires exact feed-host identity and employer identity observed inside at least
one returned position.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import unicodedata
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from src.connectors.personio import extract_positions, first_text, normalize_target_key
from src.search_intelligence.ats_delegation_evidence import ValidatedATSAuthority
from src.search_intelligence.ats_provider_registry import recognize_ats_provider
from src.search_intelligence.origin_registered_identity_contract import (
    REGISTERED_ORIGIN_IDENTITY_ALIASES,
)


PERSONIO_TARGET_AUTHORITY_VERSION = "LLM-BOOST-001.personio-target-authority.v1"
_COMPANY_FIELDS = {"subcompany", "company", "legalentity"}
_GENERIC_LEGAL_TOKENS = {
    "ag",
    "co",
    "company",
    "gmbh",
    "kg",
    "mbh",
    "se",
    "und",
}


@dataclass(frozen=True)
class PersonioTargetAuthorityEvidence:
    contract_version: str
    target_key: str | None
    requested_url: str
    final_url: str
    expected_host: str | None
    observed_host: str
    host_identity_valid: bool
    xml_valid: bool
    position_count: int
    observed_company_names: tuple[str, ...]
    matched_company_name: str | None
    matched_employer_alias: str | None
    employer_identity_bound: bool
    authority_validated: bool
    next_action: str
    reason_codes: tuple[str, ...]
    evidence_fingerprint: str
    product_authority: bool = False

    def to_validated_authority(self) -> ValidatedATSAuthority | None:
        if not self.authority_validated or self.target_key is None:
            return None
        return ValidatedATSAuthority(
            provider="personio",
            target_key=self.target_key,
            employer_identity_bound=True,
            evidence_ref=f"personio-target-authority:{self.evidence_fingerprint}",
        )

    def to_json(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "target_key": self.target_key,
            "requested_url": self.requested_url,
            "final_url": self.final_url,
            "expected_host": self.expected_host,
            "observed_host": self.observed_host,
            "host_identity_valid": self.host_identity_valid,
            "xml_valid": self.xml_valid,
            "position_count": self.position_count,
            "observed_company_names": list(self.observed_company_names),
            "matched_company_name": self.matched_company_name,
            "matched_employer_alias": self.matched_employer_alias,
            "employer_identity_bound": self.employer_identity_bound,
            "authority_validated": self.authority_validated,
            "next_action": self.next_action,
            "reason_codes": list(self.reason_codes),
            "evidence_fingerprint": self.evidence_fingerprint,
            "product_authority": self.product_authority,
        }


def _ascii_words(value: str) -> tuple[str, ...]:
    folded = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    words = tuple(re.findall(r"[a-z0-9]+", folded.casefold()))
    return tuple(word for word in words if word not in _GENERIC_LEGAL_TOKENS)


def _compact(value: str) -> str:
    return "".join(_ascii_words(value))


def _identity_aliases(
    *,
    company_key: str,
    company_name: str,
    employer_aliases: tuple[str, ...],
) -> tuple[str, ...]:
    ordered = (
        company_name,
        *REGISTERED_ORIGIN_IDENTITY_ALIASES.get(company_key, ()),
        *employer_aliases,
    )
    return tuple(dict.fromkeys(alias.strip() for alias in ordered if alias and alias.strip()))


def _match_employer_identity(
    company_names: tuple[str, ...],
    aliases: tuple[str, ...],
) -> tuple[str | None, str | None]:
    for company_name in company_names:
        company_compact = _compact(company_name)
        company_words = set(_ascii_words(company_name))
        if not company_compact:
            continue
        for alias in aliases:
            alias_compact = _compact(alias)
            alias_words = set(_ascii_words(alias))
            if len(alias_compact) < 5:
                continue
            if alias_compact == company_compact:
                return company_name, alias
            if alias_compact in company_compact and len(alias_compact) >= 7:
                return company_name, alias
            if alias_words and alias_words.issubset(company_words):
                return company_name, alias
    return None, None


def _fingerprint(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_personio_target_authority(
    *,
    candidate_url: str,
    requested_url: str,
    final_url: str,
    xml_content: bytes,
    company_key: str,
    company_name: str,
    employer_aliases: tuple[str, ...] = (),
) -> PersonioTargetAuthorityEvidence:
    """Validate exact Personio target identity plus employer identity in XML."""

    recognition = recognize_ats_provider(candidate_url)
    target_key = recognition.target_hint if recognition and recognition.provider == "personio" else None
    expected_host = f"{target_key}.jobs.personio.de" if target_key else None
    observed_host = (urlparse(final_url).hostname or "").casefold().rstrip(".")
    requested_host = (urlparse(requested_url).hostname or "").casefold().rstrip(".")
    host_identity_valid = bool(
        expected_host
        and observed_host == expected_host
        and requested_host == expected_host
        and recognition is not None
        and recognition.provider == "personio"
        and normalize_target_key(expected_host) == target_key
    )

    reason_codes: list[str] = []
    if target_key is None:
        reason_codes.append("personio_target_not_recognized")
    if not host_identity_valid:
        reason_codes.append("personio_exact_feed_host_identity_not_proven")

    xml_valid = False
    company_names: tuple[str, ...] = ()
    position_count = 0
    try:
        positions = extract_positions(xml_content)
        xml_valid = True
        position_count = len(positions)
        company_names = tuple(
            sorted(
                {
                    value
                    for position in positions
                    if (value := first_text(position, _COMPANY_FIELDS))
                },
                key=str.casefold,
            )
        )
    except (ET.ParseError, UnicodeError, ValueError):
        positions = []
        reason_codes.append("personio_xml_invalid")

    if xml_valid and position_count == 0:
        reason_codes.append("personio_xml_has_no_positions")
    if xml_valid and position_count > 0 and not company_names:
        reason_codes.append("personio_positions_lack_company_identity")

    aliases = _identity_aliases(
        company_key=company_key,
        company_name=company_name,
        employer_aliases=employer_aliases,
    )
    matched_company, matched_alias = _match_employer_identity(company_names, aliases)
    employer_identity_bound = matched_company is not None
    if company_names and not employer_identity_bound:
        reason_codes.append("personio_company_identity_does_not_match_employer")
    if employer_identity_bound:
        reason_codes.append("personio_position_company_matches_employer_identity")
    if host_identity_valid:
        reason_codes.append("personio_exact_target_feed_host_proven")

    authority_validated = bool(
        host_identity_valid
        and xml_valid
        and position_count > 0
        and employer_identity_bound
        and target_key
    )
    next_action = (
        "use_validated_personio_target_authority"
        if authority_validated
        else "retain_personio_target_authority_required"
    )
    fingerprint_payload: dict[str, object] = {
        "target_key": target_key,
        "requested_url": requested_url,
        "final_url": final_url,
        "expected_host": expected_host,
        "observed_host": observed_host,
        "host_identity_valid": host_identity_valid,
        "xml_valid": xml_valid,
        "position_count": position_count,
        "observed_company_names": company_names,
        "matched_company_name": matched_company,
        "matched_employer_alias": matched_alias,
        "employer_identity_bound": employer_identity_bound,
        "authority_validated": authority_validated,
        "reason_codes": tuple(sorted(reason_codes)),
    }
    return PersonioTargetAuthorityEvidence(
        contract_version=PERSONIO_TARGET_AUTHORITY_VERSION,
        target_key=target_key,
        requested_url=requested_url,
        final_url=final_url,
        expected_host=expected_host,
        observed_host=observed_host,
        host_identity_valid=host_identity_valid,
        xml_valid=xml_valid,
        position_count=position_count,
        observed_company_names=company_names,
        matched_company_name=matched_company,
        matched_employer_alias=matched_alias,
        employer_identity_bound=employer_identity_bound,
        authority_validated=authority_validated,
        next_action=next_action,
        reason_codes=tuple(sorted(reason_codes)),
        evidence_fingerprint=_fingerprint(fingerprint_payload),
        product_authority=False,
    )


__all__ = [
    "PERSONIO_TARGET_AUTHORITY_VERSION",
    "PersonioTargetAuthorityEvidence",
    "validate_personio_target_authority",
]
