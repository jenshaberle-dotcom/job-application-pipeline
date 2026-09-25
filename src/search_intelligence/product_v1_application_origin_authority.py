"""Employer-Origin source authority for the Product V1 application workspace.

F6 must not infer Employer-Origin authority from a browser URL or a Silver label.

The Application Workspace consumes already-materialized Product truth. A validated,
currently active Product vacancy therefore must not become unusable merely because
its ingestion profile is no longer present in the active recurring registry. The
recurring SourceRole contract remains a strong upstream admission proof, but it is
not the only downstream F6 authority.

This module composes active recurring authority, source-neutral persisted Product
origin validation for current direct vacancies, and the stricter reviewed legacy
Personio feed contract. No path grants application, submission or send authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from src.search_intelligence.personio_legacy_authority_bindings import (
    reviewed_personio_authority_binding,
)


PERSONIO_RECURRING_AUTHORITY_CONTRACT = "personio-recurring-feed-authority.v1"
ATS_BACKED_SOURCE_TYPE = "employer_origin_ats_backed_career_site"
DIRECT_EMPLOYER_ORIGIN_SOURCE_TYPES = frozenset(
    {
        "employer_origin",
        "employer_origin_career_site",
        ATS_BACKED_SOURCE_TYPE,
    }
)
AGGREGATOR_HOST_SUFFIXES = (
    "arbeitsagentur.de",
    "gute-jobs.de",
    "stepstone.de",
    "indeed.com",
    "linkedin.com",
)
AGGREGATOR_SOURCE_FAMILIES = frozenset(
    {
        "bundesagentur_fuer_arbeit",
        "gute_jobs",
        "gute-jobs",
        "stepstone",
        "indeed",
        "linkedin",
    }
)


@dataclass(frozen=True)
class ApplicationEmployerOriginAuthority:
    authorized: bool
    reason: str


def _text(value: object) -> str:
    return str(value or "").strip()


def _source_family(source_name: object) -> str:
    return _text(source_name).casefold().split(":", 1)[0]


def _https_non_aggregator_source(row: Mapping[str, object]) -> bool:
    source_url = _text(row.get("source_url"))
    parsed = urlsplit(source_url)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.casefold()
    if any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in AGGREGATOR_HOST_SUFFIXES
    ):
        return False
    return _source_family(row.get("source_name")) not in AGGREGATOR_SOURCE_FAMILIES


def _validated_product_origin_authority(
    row: Mapping[str, object],
) -> ApplicationEmployerOriginAuthority:
    """Reuse persisted Product origin truth without depending on profile liveness.

    origin_validation_status=validated is already the downstream Product statement
    that the vacancy employer origin passed the approved assessment boundary. F6
    still independently requires a current active lifecycle and a direct HTTPS
    target and rejects known discovery/aggregator sources.

    If an exact positive observation is present it must remain URL-bound. Absence
    of that optional observation does not revoke persisted Product origin truth,
    because the generation action performs its own exact vacancy revalidation
    immediately before any Codex request.
    """

    if _text(row.get("origin_validation_status")) != "validated":
        return ApplicationEmployerOriginAuthority(False, "product_origin_not_validated")
    if _text(row.get("lifecycle_status")) != "active_confirmed":
        return ApplicationEmployerOriginAuthority(
            False,
            "product_origin_lifecycle_not_active",
        )
    activity_status = _text(row.get("activity_status"))
    if activity_status and activity_status != "active":
        return ApplicationEmployerOriginAuthority(
            False,
            "product_origin_activity_not_active",
        )
    if not _https_non_aggregator_source(row):
        return ApplicationEmployerOriginAuthority(
            False,
            "validated_origin_requires_direct_https_source",
        )

    canonical_source_type = _text(row.get("canonical_source_type"))
    if canonical_source_type in {"aggregator", "discovery", "job_board"}:
        return ApplicationEmployerOriginAuthority(
            False,
            "validated_origin_cannot_use_discovery_source_type",
        )

    source_url = _text(row.get("source_url"))
    observation_url = _text(row.get("latest_observation_source_url"))
    normalized = row.get("latest_observation_evidence")
    if observation_url and observation_url != source_url:
        return ApplicationEmployerOriginAuthority(
            False,
            "current_observation_url_mismatch",
        )
    if isinstance(normalized, Mapping):
        normalized_url = _text(normalized.get("source_url"))
        if normalized_url and normalized_url != source_url:
            return ApplicationEmployerOriginAuthority(
                False,
                "current_normalized_observation_url_mismatch",
            )

    return ApplicationEmployerOriginAuthority(
        True,
        "validated_active_product_employer_origin",
    )


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
    """Return source-neutral Product F6 Employer-Origin authority."""

    if generic_source_authorized:
        return ApplicationEmployerOriginAuthority(
            True,
            "active_recurring_generic_employer_origin",
        )

    product_origin = _validated_product_origin_authority(row)
    if product_origin.authorized:
        return product_origin

    # Legacy reviewed Personio observations remain a compatibility authority for
    # older rows that predate source-neutral Product origin materialization.
    personio = _reviewed_personio_observation_authority(row)
    if personio.authorized:
        return personio

    # Preserve the most useful source-neutral blocker reason except when an
    # actual Personio target reached the stricter legacy contract and failed it.
    if _text(row.get("source_name")).startswith("personio:"):
        return personio
    return product_origin


__all__ = [
    "AGGREGATOR_HOST_SUFFIXES",
    "AGGREGATOR_SOURCE_FAMILIES",
    "ATS_BACKED_SOURCE_TYPE",
    "DIRECT_EMPLOYER_ORIGIN_SOURCE_TYPES",
    "ApplicationEmployerOriginAuthority",
    "PERSONIO_RECURRING_AUTHORITY_CONTRACT",
    "application_employer_origin_authority",
]
