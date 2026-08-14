"""Deterministic ATS delegation evidence fusion for LLM-BOOST-001.

The contract separates three layers that must never collapse into one another:
1. provider recognition;
2. employer-backed tenant/board authority;
3. delegation permission.

No network/provider/database/product effects occur here.  A validated authority
object is an input produced by a provider-specific deterministic validator, not
something inferred from a hostname by this module.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable

from src.search_intelligence.ats_provider_registry import (
    ATSProviderRecognition,
    recognize_ats_provider,
)


ATS_DELEGATION_CONTRACT_VERSION = "LLM-BOOST-001.ats-delegation-evidence.v1"


@dataclass(frozen=True)
class ValidatedATSAuthority:
    """Provider-specific authority proof already established elsewhere."""

    provider: str
    target_key: str
    employer_identity_bound: bool
    evidence_ref: str


@dataclass(frozen=True)
class ATSDelegationEvidence:
    contract_version: str
    classification: str
    provider: str | None
    recognized_urls: tuple[str, ...]
    target_hints: tuple[str, ...]
    employer_backed_urls: tuple[str, ...]
    provider_recognized: bool
    employer_backed_provider_binding: bool
    tenant_authority: bool
    delegation_permitted: bool
    semantic_booster_eligible: bool
    next_action: str
    reason_codes: tuple[str, ...]
    authority_evidence_ref: str | None
    evidence_fingerprint: str
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "classification": self.classification,
            "provider": self.provider,
            "recognized_urls": list(self.recognized_urls),
            "target_hints": list(self.target_hints),
            "employer_backed_urls": list(self.employer_backed_urls),
            "provider_recognized": self.provider_recognized,
            "employer_backed_provider_binding": self.employer_backed_provider_binding,
            "tenant_authority": self.tenant_authority,
            "delegation_permitted": self.delegation_permitted,
            "semantic_booster_eligible": self.semantic_booster_eligible,
            "next_action": self.next_action,
            "reason_codes": list(self.reason_codes),
            "authority_evidence_ref": self.authority_evidence_ref,
            "evidence_fingerprint": self.evidence_fingerprint,
            "product_authority": self.product_authority,
        }


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value}))


def _fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _recognitions(urls: Iterable[str]) -> list[tuple[str, ATSProviderRecognition]]:
    recognized: list[tuple[str, ATSProviderRecognition]] = []
    for url in _dedupe(urls):
        match = recognize_ats_provider(url)
        if match is not None:
            recognized.append((url, match))
    return recognized


def analyze_ats_delegation(
    *,
    candidate_urls: Iterable[str],
    employer_backed_urls: Iterable[str] = (),
    validated_authority: ValidatedATSAuthority | None = None,
) -> ATSDelegationEvidence:
    """Fuse ATS evidence without allowing recognition to become authority."""

    candidate_urls_tuple = _dedupe(candidate_urls)
    employer_backed_tuple = _dedupe(employer_backed_urls)
    recognized = _recognitions(candidate_urls_tuple)
    recognized_urls = _dedupe(url for url, _ in recognized)
    providers = sorted({match.provider for _, match in recognized})
    target_hints = _dedupe(
        match.target_hint
        for _, match in recognized
        if match.target_hint is not None
    )

    employer_recognized = _recognitions(employer_backed_tuple)
    employer_provider_pairs = {
        (match.provider, match.target_hint)
        for _, match in employer_recognized
    }

    provider: str | None = providers[0] if len(providers) == 1 else None
    provider_recognized = provider is not None
    reason_codes: list[str] = []
    authority_ref: str | None = None

    if not recognized:
        classification = "ats_provider_unrecognized"
        next_action = "external_ats_information_eligible"
        semantic_booster_eligible = True
        employer_binding = False
        tenant_authority = False
        delegation_permitted = False
        reason_codes.append("no_known_ats_provider_in_candidate_evidence")
    elif len(providers) > 1:
        classification = "ats_provider_conflict"
        next_action = "resolve_provider_conflict_deterministically"
        semantic_booster_eligible = False
        employer_binding = False
        tenant_authority = False
        delegation_permitted = False
        reason_codes.append("multiple_known_ats_providers_present")
    else:
        assert provider is not None
        provider_matches = [match for _, match in recognized if match.provider == provider]
        next_authority_action = provider_matches[0].next_action
        matching_employer_pairs = {
            pair
            for pair in employer_provider_pairs
            if pair[0] == provider
        }
        employer_binding = bool(matching_employer_pairs)

        authority_matches = False
        if validated_authority is not None:
            authority_matches = (
                validated_authority.provider == provider
                and validated_authority.employer_identity_bound
                and bool(validated_authority.evidence_ref)
                and validated_authority.target_key in target_hints
                and (provider, validated_authority.target_key) in matching_employer_pairs
            )

        if authority_matches:
            classification = "ats_delegation_ready"
            next_action = "delegate_to_validated_provider_target"
            semantic_booster_eligible = False
            tenant_authority = True
            delegation_permitted = True
            authority_ref = validated_authority.evidence_ref if validated_authority else None
            reason_codes.extend(
                (
                    "known_provider_recognized",
                    "employer_backed_provider_target_present",
                    "provider_specific_authority_validated",
                )
            )
        elif employer_binding:
            classification = "ats_provider_target_authority_required"
            next_action = next_authority_action
            semantic_booster_eligible = False
            tenant_authority = False
            delegation_permitted = False
            reason_codes.extend(
                (
                    "known_provider_recognized",
                    "employer_backed_provider_evidence_present",
                    "provider_specific_authority_not_validated",
                )
            )
        else:
            classification = "ats_provider_recognized_binding_required"
            next_action = next_authority_action
            semantic_booster_eligible = False
            tenant_authority = False
            delegation_permitted = False
            reason_codes.extend(
                (
                    "known_provider_recognized",
                    "employer_backed_provider_binding_missing",
                )
            )

    fingerprint_payload: dict[str, object] = {
        "candidate_urls": candidate_urls_tuple,
        "recognized_urls": recognized_urls,
        "providers": providers,
        "target_hints": target_hints,
        "employer_backed_urls": employer_backed_tuple,
        "classification": classification,
        "next_action": next_action,
        "reason_codes": tuple(sorted(reason_codes)),
        "authority_evidence_ref": authority_ref,
    }
    return ATSDelegationEvidence(
        contract_version=ATS_DELEGATION_CONTRACT_VERSION,
        classification=classification,
        provider=provider,
        recognized_urls=recognized_urls,
        target_hints=target_hints,
        employer_backed_urls=employer_backed_tuple,
        provider_recognized=provider_recognized,
        employer_backed_provider_binding=employer_binding,
        tenant_authority=tenant_authority,
        delegation_permitted=delegation_permitted,
        semantic_booster_eligible=semantic_booster_eligible,
        next_action=next_action,
        reason_codes=tuple(sorted(reason_codes)),
        authority_evidence_ref=authority_ref,
        evidence_fingerprint=_fingerprint(fingerprint_payload),
        product_authority=False,
    )


__all__ = [
    "ATS_DELEGATION_CONTRACT_VERSION",
    "ATSDelegationEvidence",
    "ValidatedATSAuthority",
    "analyze_ats_delegation",
]
