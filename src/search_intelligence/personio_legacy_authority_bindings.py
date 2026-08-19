"""Reviewed authority bindings for legacy Personio sources.

These two targets were activated before the current employer-origin candidate/gate
model existed. Runtime #203 later proved, with bounded public XML shadows, that the
existing deterministic Personio target-authority validator binds both tenants to
the expected employers. This module records only those reviewed migration facts.

It is intentionally not a generic hostname allowlist: unlisted Personio targets
receive no recurring lifecycle authority from this contract.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewedPersonioAuthorityBinding:
    target_key: str
    company_key: str
    company_name: str
    employer_aliases: tuple[str, ...]
    evidence_contract: str = "runtime_203_personio_target_authority_shadow_v1"


REVIEWED_LEGACY_PERSONIO_AUTHORITY_BINDINGS: dict[
    str, ReviewedPersonioAuthorityBinding
] = {
    "1komma5grad": ReviewedPersonioAuthorityBinding(
        target_key="1komma5grad",
        company_key="legacy_personio_1komma5grad",
        company_name="1KOMMA5° GmbH",
        employer_aliases=("1KOMMA5", "1KOMMA5°"),
    ),
    "eraneos": ReviewedPersonioAuthorityBinding(
        target_key="eraneos",
        company_key="legacy_personio_eraneos",
        company_name="Eraneos Analytics Germany GmbH",
        employer_aliases=("Eraneos",),
    ),
}


def reviewed_personio_authority_binding(
    target_key: str,
) -> ReviewedPersonioAuthorityBinding | None:
    return REVIEWED_LEGACY_PERSONIO_AUTHORITY_BINDINGS.get(target_key)
