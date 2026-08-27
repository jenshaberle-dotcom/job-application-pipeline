"""Deterministic lifecycle absence from verified complete inventories.

A full-fetch connector capability is never inventory authority by itself.

The current implementation recognizes only the already-reviewed Personio
recurring authority contract used by migration 099. Invalid, empty, mixed,
unreviewed or identity-incomplete inventories return no authority and therefore
fall back to exact-detail lifecycle reconciliation.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.connectors.base import RawJobRecord
from src.job_lifecycle_health import (
    COVERAGE_COMPLETE_INVENTORY,
    OUTCOME_NOT_SEEN,
    HealthClassification,
    JobHealthTarget,
    JobLifecycleHealthRepository,
    normalize_url_identity,
)
from src.search_intelligence.personio_legacy_authority_bindings import (
    reviewed_personio_authority_binding,
)
from src.search_intelligence.personio_target_authority import (
    PERSONIO_TARGET_AUTHORITY_VERSION,
)


PERSONIO_RECURRING_AUTHORITY_CONTRACT = (
    "personio-recurring-feed-authority.v1"
)
ATS_BACKED_SOURCE_TYPE = "employer_origin_ats_backed_career_site"

COMPLETE_INVENTORY_OBSERVER = (
    "recurring_ingestion_verified_complete_inventory"
)

MAX_COMPLETE_INVENTORY_ABSENCES = 20


@dataclass(frozen=True)
class VerifiedCompleteInventoryAuthority:
    provider: str
    target_key: str
    contract_version: str
    reviewed_binding_contract: str
    validator_contract_version: str
    evidence_fingerprint: str
    matched_company_name: str
    position_count: int
    requested_url: str
    final_url: str
    http_status_code: int


@dataclass(frozen=True)
class CompleteInventoryAbsencePlan:
    authority: VerifiedCompleteInventoryAuthority
    target_count: int
    observed_target_ids: tuple[int, ...]
    missing_targets: tuple[JobHealthTarget, ...]


@dataclass(frozen=True)
class CompleteInventoryLifecycleSummary:
    authority_target_key: str
    authority_evidence_fingerprint: str
    target_count: int
    observed_target_count: int
    missing_target_count: int
    not_seen_write_count: int
    written_observation_ids: tuple[int, ...]


def _string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value > 0 else None


def _http_status(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 200 <= value < 400 else None


def _normalized_url(value: str) -> str:
    if not value.strip():
        return ""
    return normalize_url_identity(value)


def _authority_from_record(
    *,
    source_name: str,
    record: RawJobRecord,
) -> VerifiedCompleteInventoryAuthority | None:
    if record.source_name != source_name:
        return None

    raw = record.raw_data
    if raw.get("source_type") != ATS_BACKED_SOURCE_TYPE:
        return None

    authority = raw.get("ats_feed_authority")
    source_target = raw.get("source_target")
    job = raw.get("job")

    if not isinstance(authority, dict):
        return None
    if not isinstance(source_target, dict):
        return None
    if not isinstance(job, dict):
        return None

    provider = _string(authority.get("provider"))
    target_key = _string(authority.get("target_key"))
    contract_version = _string(authority.get("contract_version"))
    reviewed_contract = _string(
        authority.get("reviewed_binding_contract")
    )
    validator_contract = _string(
        authority.get("validator_contract_version")
    )
    evidence_fingerprint = _string(
        authority.get("evidence_fingerprint")
    )
    matched_company_name = _string(
        authority.get("matched_company_name")
    )
    requested_url = _string(authority.get("requested_url"))
    final_url = _string(authority.get("final_url"))
    position_count = _positive_int(authority.get("position_count"))
    status_code = _http_status(authority.get("http_status_code"))

    if (
        provider != "personio"
        or target_key is None
        or contract_version != PERSONIO_RECURRING_AUTHORITY_CONTRACT
        or validator_contract != PERSONIO_TARGET_AUTHORITY_VERSION
        or evidence_fingerprint is None
        or matched_company_name is None
        or requested_url is None
        or final_url is None
        or position_count is None
        or status_code is None
    ):
        return None

    binding = reviewed_personio_authority_binding(target_key)
    if binding is None:
        return None

    if reviewed_contract != binding.evidence_contract:
        return None

    if source_name != f"personio:{target_key}":
        return None

    if _string(source_target.get("target_key")) != target_key:
        return None

    record_source_url = _string(record.source_url)
    job_source_url = _string(job.get("source_url"))
    if record_source_url is None or job_source_url != record_source_url:
        return None

    if authority.get("authority_validated") is not True:
        return None
    if authority.get("employer_identity_bound") is not True:
        return None
    if authority.get("feed_inventory_complete") is not True:
        return None
    if authority.get("product_authority") is not False:
        return None

    return VerifiedCompleteInventoryAuthority(
        provider=provider,
        target_key=target_key,
        contract_version=contract_version,
        reviewed_binding_contract=reviewed_contract,
        validator_contract_version=validator_contract,
        evidence_fingerprint=evidence_fingerprint,
        matched_company_name=matched_company_name,
        position_count=position_count,
        requested_url=requested_url,
        final_url=final_url,
        http_status_code=status_code,
    )


def _concrete_inventory_url(
    value: str,
    *,
    authority: VerifiedCompleteInventoryAuthority,
) -> str | None:
    normalized = _normalized_url(value)
    if not normalized:
        return None

    feed_urls = {
        _normalized_url(authority.requested_url),
        _normalized_url(authority.final_url),
    }
    if normalized in feed_urls:
        return None

    return normalized


def verified_complete_inventory_authority(
    *,
    source_name: str,
    records: Sequence[RawJobRecord],
) -> VerifiedCompleteInventoryAuthority | None:
    """Return authority only for one internally consistent current inventory."""

    source_name = source_name.strip()
    if not source_name or not records:
        return None

    authorities: list[VerifiedCompleteInventoryAuthority] = []

    for record in records:
        authority = _authority_from_record(
            source_name=source_name,
            record=record,
        )
        if authority is None:
            return None
        authorities.append(authority)

    first = authorities[0]
    if any(authority != first for authority in authorities[1:]):
        return None

    if first.position_count != len(records):
        return None

    seen_external_ids: set[str] = set()
    seen_urls: set[str] = set()

    for record in records:
        external_id = (
            record.external_job_id.strip()
            if record.external_job_id
            else ""
        )
        concrete_url = _concrete_inventory_url(
            record.source_url,
            authority=first,
        )

        if not external_id and concrete_url is None:
            return None

        if external_id:
            if external_id in seen_external_ids:
                return None
            seen_external_ids.add(external_id)

        if concrete_url is not None:
            if concrete_url in seen_urls:
                return None
            seen_urls.add(concrete_url)

    return first


def plan_verified_complete_inventory_absences(
    *,
    source_name: str,
    authority: VerifiedCompleteInventoryAuthority,
    records: Sequence[RawJobRecord],
    targets: Sequence[JobHealthTarget],
    max_absences: int = MAX_COMPLETE_INVENTORY_ABSENCES,
) -> CompleteInventoryAbsencePlan | None:
    """Plan authoritative absences without writing or performing network calls."""

    if max_absences <= 0:
        raise ValueError("max_absences must be positive")

    observed_external_ids = {
        record.external_job_id.strip()
        for record in records
        if record.external_job_id and record.external_job_id.strip()
    }

    observed_urls = {
        concrete_url
        for record in records
        if (
            concrete_url := _concrete_inventory_url(
                record.source_url,
                authority=authority,
            )
        )
        is not None
    }

    observed_target_ids: list[int] = []
    missing_targets: list[JobHealthTarget] = []

    for target in targets:
        if target.source_name != source_name:
            return None

        external_id = (
            target.external_job_id.strip()
            if target.external_job_id
            else ""
        )
        target_url = _concrete_inventory_url(
            target.source_url,
            authority=authority,
        )

        if not external_id and target_url is None:
            return None

        observed = bool(
            external_id
            and external_id in observed_external_ids
        )

        if not observed and target_url is not None:
            observed = target_url in observed_urls

        if observed:
            observed_target_ids.append(target.silver_job_id)
        else:
            missing_targets.append(target)

    if len(missing_targets) > max_absences:
        raise RuntimeError(
            "verified complete inventory absence exceeds bounded write cap: "
            f"missing={len(missing_targets)} "
            f"max_absences={max_absences}"
        )

    return CompleteInventoryAbsencePlan(
        authority=authority,
        target_count=len(targets),
        observed_target_ids=tuple(observed_target_ids),
        missing_targets=tuple(missing_targets),
    )


def _not_seen_classification(
    *,
    authority: VerifiedCompleteInventoryAuthority,
    current_record_count: int,
) -> HealthClassification:
    return HealthClassification(
        outcome=OUTCOME_NOT_SEEN,
        coverage=COVERAGE_COMPLETE_INVENTORY,
        evidence_reason=(
            "authoritative_verified_ats_complete_inventory_absence"
        ),
        evidence={
            "provider": authority.provider,
            "target_key": authority.target_key,
            "authority_contract_version": authority.contract_version,
            "reviewed_binding_contract": (
                authority.reviewed_binding_contract
            ),
            "validator_contract_version": (
                authority.validator_contract_version
            ),
            "evidence_fingerprint": authority.evidence_fingerprint,
            "matched_company_name": authority.matched_company_name,
            "position_count": authority.position_count,
            "current_record_count": current_record_count,
            "http_status_code": authority.http_status_code,
            "requested_url": authority.requested_url,
            "final_url": authority.final_url,
            "product_authority": False,
            "raw_inventory_persisted": False,
        },
    )


def reconcile_verified_complete_inventory_health(
    *,
    health_repository: JobLifecycleHealthRepository,
    source_name: str,
    observed_records: Sequence[RawJobRecord],
    ingestion_run_id: int,
    max_absences: int = MAX_COMPLETE_INVENTORY_ABSENCES,
) -> CompleteInventoryLifecycleSummary | None:
    """Apply complete-inventory absence authority or return None for fallback."""

    if ingestion_run_id <= 0:
        raise ValueError("ingestion_run_id must be positive")

    authority = verified_complete_inventory_authority(
        source_name=source_name,
        records=observed_records,
    )
    if authority is None:
        return None

    targets = (
        health_repository
        .load_active_targets_for_verified_complete_inventory_source(
            source_name.strip()
        )
    )

    plan = plan_verified_complete_inventory_absences(
        source_name=source_name.strip(),
        authority=authority,
        records=observed_records,
        targets=targets,
        max_absences=max_absences,
    )
    if plan is None:
        return None

    expected_classifications = [
        (
            target,
            _not_seen_classification(
                authority=authority,
                current_record_count=len(observed_records),
            ),
        )
        for target in plan.missing_targets
    ]

    written_ids = (
        health_repository.append_complete_inventory_absence_batch(
            expected_classifications=expected_classifications,
            expected_source_name=source_name.strip(),
            observed_by=COMPLETE_INVENTORY_OBSERVER,
            ingestion_run_id=ingestion_run_id,
        )
        if expected_classifications
        else []
    )

    return CompleteInventoryLifecycleSummary(
        authority_target_key=authority.target_key,
        authority_evidence_fingerprint=(
            authority.evidence_fingerprint
        ),
        target_count=plan.target_count,
        observed_target_count=len(plan.observed_target_ids),
        missing_target_count=len(plan.missing_targets),
        not_seen_write_count=len(written_ids),
        written_observation_ids=tuple(written_ids),
    )
