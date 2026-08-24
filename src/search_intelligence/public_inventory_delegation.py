"""Fail-closed one-hop authority for explicit public ATS inventory surfaces.

This module turns neither ATS recognition nor a cross-host link into authority on
its own.  It accepts only an already-authorized employer page that explicitly
loaded a provider-recognized public inventory bundle, plus a candidate URL
observed from that exact inventory host.  The returned host authority is a bounded
fetch permission only; genuine-job/content proof remains a separate downstream
gate and Product authority is never granted here.

The contract is intentionally network-free and provider-generic.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable
from urllib.parse import urlparse

from src.search_intelligence.ats_provider_registry import recognize_ats_provider


PUBLIC_INVENTORY_DELEGATION_VERSION = "ACQ-RUNTIME-001.public-inventory-delegation.v1"
_ALLOWED_ROUTE_KINDS = frozenset({"public_widget_bundle"})


@dataclass(frozen=True)
class PublicInventoryDelegationEvidence:
    contract_version: str
    employer_page_host: str
    inventory_host: str
    candidate_host: str
    provider: str | None
    route_kind: str
    employer_page_authorized: bool
    inventory_provider_recognized: bool
    candidate_provider_recognized: bool
    exact_inventory_candidate_host_match: bool
    provider_consistent: bool
    delegation_permitted: bool
    delegated_host: str | None
    reason_codes: tuple[str, ...]
    evidence_fingerprint: str
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "employer_page_host": self.employer_page_host,
            "inventory_host": self.inventory_host,
            "candidate_host": self.candidate_host,
            "provider": self.provider,
            "route_kind": self.route_kind,
            "employer_page_authorized": self.employer_page_authorized,
            "inventory_provider_recognized": self.inventory_provider_recognized,
            "candidate_provider_recognized": self.candidate_provider_recognized,
            "exact_inventory_candidate_host_match": self.exact_inventory_candidate_host_match,
            "provider_consistent": self.provider_consistent,
            "delegation_permitted": self.delegation_permitted,
            "delegated_host": self.delegated_host,
            "reason_codes": list(self.reason_codes),
            "evidence_fingerprint": self.evidence_fingerprint,
            "product_authority": self.product_authority,
        }


def _host(value: str) -> str:
    parsed = urlparse(str(value or ""))
    return (parsed.hostname or "").casefold().strip(".")


def _https(value: str) -> bool:
    parsed = urlparse(str(value or ""))
    return parsed.scheme.casefold() == "https" and bool(parsed.hostname)


def _authorized(host: str, authorized_hosts: Iterable[str]) -> bool:
    normalized = {
        str(item).casefold().strip(".")
        for item in authorized_hosts
        if str(item).strip()
    }
    return bool(host and host in normalized)


def _fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def authorize_public_inventory_candidate_host(
    *,
    employer_page_url: str,
    authorized_employer_hosts: Iterable[str],
    inventory_host: str,
    inventory_provider: str,
    route_kind: str,
    candidate_url: str,
    candidate_observation_host: str,
) -> PublicInventoryDelegationEvidence:
    """Authorize one exact public inventory host for one observed candidate.

    ``inventory_host`` and ``route_kind`` are expected to come from explicit
    bounded static/widget evidence. ``candidate_observation_host`` is expected to
    come from bounded runtime observation.  The function does not infer either.
    Candidate content must still pass the existing genuine-job proof after fetch.
    """

    page_host = _host(employer_page_url)
    normalized_inventory_host = str(inventory_host or "").casefold().strip(".")
    normalized_observation_host = str(candidate_observation_host or "").casefold().strip(".")
    candidate_host = _host(candidate_url)
    route_kind = str(route_kind or "").strip()
    inventory_provider = str(inventory_provider or "").strip().casefold()

    page_authorized = bool(
        _https(employer_page_url)
        and _authorized(page_host, authorized_employer_hosts)
    )
    inventory_recognition = recognize_ats_provider(normalized_inventory_host)
    candidate_recognition = recognize_ats_provider(candidate_url)
    inventory_provider_recognized = bool(
        inventory_recognition is not None
        and inventory_recognition.provider == inventory_provider
    )
    candidate_provider_recognized = bool(
        candidate_recognition is not None
        and candidate_recognition.provider == inventory_provider
    )
    exact_host_match = bool(
        normalized_inventory_host
        and candidate_host == normalized_inventory_host
        and normalized_observation_host == normalized_inventory_host
    )
    provider_consistent = bool(
        inventory_provider_recognized
        and candidate_provider_recognized
        and inventory_recognition is not None
        and candidate_recognition is not None
        and inventory_recognition.provider == candidate_recognition.provider
    )

    reasons: list[str] = []
    if not page_authorized:
        reasons.append("employer_page_not_currently_authorized")
    if route_kind not in _ALLOWED_ROUTE_KINDS:
        reasons.append("explicit_public_inventory_route_kind_missing")
    if not normalized_inventory_host:
        reasons.append("public_inventory_host_missing")
    if not inventory_provider_recognized:
        reasons.append("public_inventory_provider_not_recognized")
    if not _https(candidate_url):
        reasons.append("candidate_url_not_https")
    if not candidate_provider_recognized:
        reasons.append("candidate_provider_not_recognized")
    if not exact_host_match:
        reasons.append("candidate_not_observed_from_exact_inventory_host")
    if not provider_consistent:
        reasons.append("inventory_candidate_provider_mismatch")

    permitted = bool(
        page_authorized
        and route_kind in _ALLOWED_ROUTE_KINDS
        and normalized_inventory_host
        and _https(candidate_url)
        and exact_host_match
        and provider_consistent
    )
    if permitted:
        reasons.extend(
            (
                "authorized_employer_page_loaded_explicit_public_inventory",
                "candidate_observed_from_exact_public_inventory_host",
                "known_ats_provider_consistent_across_inventory_and_candidate",
            )
        )

    fingerprint_payload: dict[str, object] = {
        "employer_page_host": page_host,
        "inventory_host": normalized_inventory_host,
        "candidate_host": candidate_host,
        "candidate_observation_host": normalized_observation_host,
        "provider": inventory_provider or None,
        "route_kind": route_kind,
        "employer_page_authorized": page_authorized,
        "inventory_provider_recognized": inventory_provider_recognized,
        "candidate_provider_recognized": candidate_provider_recognized,
        "exact_inventory_candidate_host_match": exact_host_match,
        "provider_consistent": provider_consistent,
        "delegation_permitted": permitted,
        "reason_codes": tuple(sorted(reasons)),
    }
    return PublicInventoryDelegationEvidence(
        contract_version=PUBLIC_INVENTORY_DELEGATION_VERSION,
        employer_page_host=page_host,
        inventory_host=normalized_inventory_host,
        candidate_host=candidate_host,
        provider=inventory_provider or None,
        route_kind=route_kind,
        employer_page_authorized=page_authorized,
        inventory_provider_recognized=inventory_provider_recognized,
        candidate_provider_recognized=candidate_provider_recognized,
        exact_inventory_candidate_host_match=exact_host_match,
        provider_consistent=provider_consistent,
        delegation_permitted=permitted,
        delegated_host=normalized_inventory_host if permitted else None,
        reason_codes=tuple(sorted(reasons)),
        evidence_fingerprint=_fingerprint(fingerprint_payload),
        product_authority=False,
    )


__all__ = [
    "PUBLIC_INVENTORY_DELEGATION_VERSION",
    "PublicInventoryDelegationEvidence",
    "authorize_public_inventory_candidate_host",
]
