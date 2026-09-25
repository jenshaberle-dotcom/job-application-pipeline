"""Employer-Origin source authority for the Product V1 application workspace.

F6 must not infer Employer-Origin authority from a browser URL or a Silver label.
The normal product path is the active recurring generic_origin SourceRole contract.
Two reviewed legacy Personio targets predate that registry model, but their exact
recurring observations already carry a stricter deterministic authority contract
used by lifecycle migration 099.

This module composes those existing authorities without broadening Personio in
general.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from src.search_intelligence.personio_legacy_authority_bindings import (
    reviewed_personio_authority_binding,
)


PERSONIO_RECURRING_AUTHORITY_CONTRACT = "personio-recurring-feed-authority.v1"
ATS_BACKED_SOURCE_TYPE = "employer_origin_ats_backed_career_site"


@dataclass(frozen=True)
class ApplicationEmployerOriginAuthority:
    authorized: bool
    reason: str


def _text(value: object) -> str:
    return str(value or "").strip()


def _reviewed_personio_observation_authority(
    row: Mapping[str, object],
) -> ApplicationEmployerOriginAuthority:
    source_name = _text(row.get("source_name"))
    if not source_name.startswith("personio:"):
        return ApplicationEmployerOriginAuthority(False, "not_reviewed_personio")

    target_key = source_name.split(":", 1)[1]
    binding = reviewed_personio_authority_binding(target_key)
    if binding is None:
        return ApplicationEmployerOriginAuthority(
            False,
            "personio_target_not_reviewed",
        )

    if _text(row.get("lifecycle_status")) != "active_confirmed":
        return ApplicationEmployerOriginAuthority(
            False,
            "personio_lifecycle_not_active",
        )
    # Lifecycle-health evidence is intentionally independent from source-origin
    # authority. An operator-triggered exact-detail revalidation may become the
    # newest lifecycle projection without invalidating the already-bound reviewed
    # recurring-feed observation that proves Employer-Origin identity.
    source_url = _text(row.get("source_url"))
    observation_url = _text(row.get("latest_observation_source_url"))
    normalized = row.get("latest_observation_evidence")
    if not source_url or observation_url != source_url or not isinstance(normalized, Mapping):
        return ApplicationEmployerOriginAuthority(
            False,
            "personio_exact_observation_required",
        )
    if _text(normalized.get("source_url")) != source_url:
        return ApplicationEmployerOriginAuthority(
            False,
            "personio_normalized_observation_url_mismatch",
        )

    raw = normalized.get("raw_evidence")
    if not isinstance(raw, Mapping):
        return ApplicationEmployerOriginAuthority(
            False,
            "personio_raw_evidence_required",
        )
    if _text(raw.get("source_type")) != ATS_BACKED_SOURCE_TYPE:
        return ApplicationEmployerOriginAuthority(
            False,
            "personio_ats_backed_source_type_required",
        )

    authority = raw.get("ats_feed_authority")
    source_target = raw.get("source_target")
    job = raw.get("job")
    if not isinstance(authority, Mapping):
        return ApplicationEmployerOriginAuthority(
            False,
            "personio_feed_authority_required",
        )
    if not isinstance(source_target, Mapping) or not isinstance(job, Mapping):
        return ApplicationEmployerOriginAuthority(
            False,
            "personio_target_job_binding_required",
        )

    exact_contract = (
        _text(authority.get("contract_version"))
        == PERSONIO_RECURRING_AUTHORITY_CONTRACT
        and _text(authority.get("reviewed_binding_contract"))
        == binding.evidence_contract
        and _text(authority.get("provider")) == "personio"
        and _text(authority.get("target_key")) == target_key
        and authority.get("authority_validated") is True
        and authority.get("employer_identity_bound") is True
        and authority.get("feed_inventory_complete") is True
        and authority.get("product_authority") is False
        and bool(_text(authority.get("evidence_fingerprint")))
        and bool(_text(authority.get("matched_company_name")))
        and _text(source_target.get("target_key")) == target_key
        and _text(job.get("source_url")) == source_url
    )
    if not exact_contract:
        return ApplicationEmployerOriginAuthority(
            False,
            "personio_reviewed_feed_contract_mismatch",
        )

    return ApplicationEmployerOriginAuthority(
        True,
        "reviewed_verified_personio_recurring_feed",
    )


def application_employer_origin_authority(
    row: Mapping[str, object],
    *,
    generic_source_authorized: bool,
) -> ApplicationEmployerOriginAuthority:
    """Return Product F6 source authority without inventing new source classes."""

    if generic_source_authorized:
        return ApplicationEmployerOriginAuthority(
            True,
            "active_recurring_generic_employer_origin",
        )

    return _reviewed_personio_observation_authority(row)


__all__ = [
    "ATS_BACKED_SOURCE_TYPE",
    "ApplicationEmployerOriginAuthority",
    "PERSONIO_RECURRING_AUTHORITY_CONTRACT",
    "application_employer_origin_authority",
]
