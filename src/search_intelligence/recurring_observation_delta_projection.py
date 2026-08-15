"""Pure post-095 recurring-observation pair projection for LLM-BOOST-001.

This module bridges already-read ``job_observations`` metadata into truthful
pair-level delta evidence.  It performs no database access, network/provider
call, scheduler action, lifecycle transition, ranking, application or product
write.

Only observations with a non-null evidence hash and matching evidence-contract
version may be classified as unchanged or changed.  Historical rows with no
per-sighting hash are deliberately incomparable and break the comparison chain;
no history is synthesized or backfilled here.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
import re

from src.search_intelligence.recurring_connector_economics import (
    RecurringDeltaKind,
    source_local_job_identity,
)

RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION = (
    "LLM-BOOST-001.recurring-observation-delta-projection.v1"
)
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class RecurringObservationClassification(StrEnum):
    """Truth status for one observation relative to its comparison history."""

    BASELINE_ONLY = "baseline_only"
    UNCHANGED = "unchanged"
    EVIDENCE_CHANGED = "evidence_changed"
    CONTRACT_BOUNDARY = "contract_boundary"
    INCOMPARABLE_MISSING_EVIDENCE = "incomparable_missing_evidence"
    IDENTITY_MISMATCH = "identity_mismatch"
    NON_FORWARD_TIMESTAMP = "non_forward_timestamp"


@dataclass(frozen=True)
class RecurringObservationSnapshot:
    """Minimal persisted observation metadata required for truthful comparison."""

    source_name: str
    external_job_id: str | None
    source_url: str | None
    observed_at: datetime
    normalized_evidence_hash: str | None
    evidence_contract_version: str | None

    def __post_init__(self) -> None:
        if not self.source_name.strip():
            raise ValueError("source_name must be non-empty")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")

        hash_value = self.normalized_evidence_hash
        contract = self.evidence_contract_version
        if (hash_value is None) != (contract is None):
            raise ValueError("evidence hash and contract version must be both null or both present")
        if hash_value is not None and _HASH_RE.fullmatch(hash_value) is None:
            raise ValueError("normalized_evidence_hash must be a lowercase SHA-256 hex digest")
        if contract is not None and not contract.strip():
            raise ValueError("evidence_contract_version must be non-empty when hash is present")

        # Validate the source-local identity eagerly.  No fuzzy/alias matching is
        # allowed at this economic cache boundary.
        source_local_job_identity(
            external_job_id=self.external_job_id,
            source_url=self.source_url,
        )

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> "RecurringObservationSnapshot":
        """Project one already-read DB row without opening or mutating a database."""

        observed_at = row.get("observed_at")
        if not isinstance(observed_at, datetime):
            raise TypeError("observed_at must be a datetime")

        def optional_text(key: str) -> str | None:
            value = row.get(key)
            if value is None:
                return None
            if not isinstance(value, str):
                raise TypeError(f"{key} must be a string or null")
            return value

        source_name = row.get("source_name")
        if not isinstance(source_name, str):
            raise TypeError("source_name must be a string")
        return cls(
            source_name=source_name,
            external_job_id=optional_text("external_job_id"),
            source_url=optional_text("source_url"),
            observed_at=observed_at,
            normalized_evidence_hash=optional_text("normalized_evidence_hash"),
            evidence_contract_version=optional_text("evidence_contract_version"),
        )

    @property
    def source_job_identity(self) -> str:
        return source_local_job_identity(
            external_job_id=self.external_job_id,
            source_url=self.source_url,
        )

    @property
    def identity_key(self) -> str:
        return f"{self.source_name.strip()}|{self.source_job_identity}"

    @property
    def has_evidence_hash(self) -> bool:
        return self.normalized_evidence_hash is not None


@dataclass(frozen=True)
class RecurringObservationDeltaEvidence:
    """One product-neutral classification event."""

    projection_version: str
    identity_key: str
    classification: RecurringObservationClassification
    delta_kind: RecurringDeltaKind | None
    current_observed_at: datetime
    previous_observed_at: datetime | None
    evidence_contract_version: str | None
    comparable_pair: bool
    reason_code: str
    provider_model_eligible: bool = False
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["classification"] = self.classification.value
        payload["delta_kind"] = self.delta_kind.value if self.delta_kind else None
        payload["current_observed_at"] = self.current_observed_at.isoformat()
        payload["previous_observed_at"] = (
            self.previous_observed_at.isoformat() if self.previous_observed_at else None
        )
        return payload


def classify_observation_pair(
    *,
    previous: RecurringObservationSnapshot,
    current: RecurringObservationSnapshot,
) -> RecurringObservationDeltaEvidence:
    """Classify an exact previous/current pair without granting booster authority."""

    if previous.identity_key != current.identity_key:
        return RecurringObservationDeltaEvidence(
            projection_version=RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION,
            identity_key=current.identity_key,
            classification=RecurringObservationClassification.IDENTITY_MISMATCH,
            delta_kind=RecurringDeltaKind.CACHE_IDENTITY_MISMATCH,
            current_observed_at=current.observed_at,
            previous_observed_at=previous.observed_at,
            evidence_contract_version=current.evidence_contract_version,
            comparable_pair=False,
            reason_code="recurring_observation_identity_mismatch",
        )

    if current.observed_at <= previous.observed_at:
        return RecurringObservationDeltaEvidence(
            projection_version=RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION,
            identity_key=current.identity_key,
            classification=RecurringObservationClassification.NON_FORWARD_TIMESTAMP,
            delta_kind=None,
            current_observed_at=current.observed_at,
            previous_observed_at=previous.observed_at,
            evidence_contract_version=current.evidence_contract_version,
            comparable_pair=False,
            reason_code="recurring_observation_timestamp_not_forward",
        )

    if not previous.has_evidence_hash or not current.has_evidence_hash:
        return RecurringObservationDeltaEvidence(
            projection_version=RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION,
            identity_key=current.identity_key,
            classification=RecurringObservationClassification.INCOMPARABLE_MISSING_EVIDENCE,
            delta_kind=None,
            current_observed_at=current.observed_at,
            previous_observed_at=previous.observed_at,
            evidence_contract_version=current.evidence_contract_version,
            comparable_pair=False,
            reason_code="recurring_observation_pair_missing_truthful_hash_history",
        )

    if previous.evidence_contract_version != current.evidence_contract_version:
        return RecurringObservationDeltaEvidence(
            projection_version=RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION,
            identity_key=current.identity_key,
            classification=RecurringObservationClassification.CONTRACT_BOUNDARY,
            delta_kind=RecurringDeltaKind.CONTRACT_CHANGED,
            current_observed_at=current.observed_at,
            previous_observed_at=previous.observed_at,
            evidence_contract_version=current.evidence_contract_version,
            comparable_pair=False,
            reason_code="recurring_observation_evidence_contract_changed",
        )

    if previous.normalized_evidence_hash == current.normalized_evidence_hash:
        classification = RecurringObservationClassification.UNCHANGED
        delta_kind = RecurringDeltaKind.UNCHANGED
        reason_code = "recurring_observation_same_contract_hash_unchanged"
    else:
        classification = RecurringObservationClassification.EVIDENCE_CHANGED
        delta_kind = RecurringDeltaKind.EVIDENCE_CHANGED
        reason_code = "recurring_observation_same_contract_hash_changed"

    return RecurringObservationDeltaEvidence(
        projection_version=RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION,
        identity_key=current.identity_key,
        classification=classification,
        delta_kind=delta_kind,
        current_observed_at=current.observed_at,
        previous_observed_at=previous.observed_at,
        evidence_contract_version=current.evidence_contract_version,
        comparable_pair=True,
        reason_code=reason_code,
    )


def _baseline_event(snapshot: RecurringObservationSnapshot) -> RecurringObservationDeltaEvidence:
    if snapshot.has_evidence_hash:
        return RecurringObservationDeltaEvidence(
            projection_version=RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION,
            identity_key=snapshot.identity_key,
            classification=RecurringObservationClassification.BASELINE_ONLY,
            delta_kind=RecurringDeltaKind.NEW,
            current_observed_at=snapshot.observed_at,
            previous_observed_at=None,
            evidence_contract_version=snapshot.evidence_contract_version,
            comparable_pair=False,
            reason_code="first_hash_bearing_observation_is_baseline_only",
        )
    return RecurringObservationDeltaEvidence(
        projection_version=RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION,
        identity_key=snapshot.identity_key,
        classification=RecurringObservationClassification.INCOMPARABLE_MISSING_EVIDENCE,
        delta_kind=None,
        current_observed_at=snapshot.observed_at,
        previous_observed_at=None,
        evidence_contract_version=None,
        comparable_pair=False,
        reason_code="historical_observation_has_no_truthful_evidence_hash",
    )


def project_recurring_observation_deltas(
    observations: Iterable[RecurringObservationSnapshot],
) -> tuple[RecurringObservationDeltaEvidence, ...]:
    """Project an ordered observation stream into fail-closed delta evidence.

    The caller must provide observations in nondecreasing read order.  Ordering
    is checked per exact source-local identity.  A missing-hash observation or a
    non-forward timestamp breaks that identity's comparison chain, so a later
    hash-bearing sighting starts a new baseline rather than skipping over the
    untrusted gap.
    """

    events: list[RecurringObservationDeltaEvidence] = []
    previous_by_identity: dict[str, RecurringObservationSnapshot] = {}
    last_seen_at: dict[str, datetime] = {}

    for current in observations:
        identity = current.identity_key
        seen_at = last_seen_at.get(identity)
        if seen_at is not None and current.observed_at <= seen_at:
            previous = previous_by_identity.get(identity)
            previous_at = previous.observed_at if previous is not None else seen_at
            events.append(
                RecurringObservationDeltaEvidence(
                    projection_version=RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION,
                    identity_key=identity,
                    classification=RecurringObservationClassification.NON_FORWARD_TIMESTAMP,
                    delta_kind=None,
                    current_observed_at=current.observed_at,
                    previous_observed_at=previous_at,
                    evidence_contract_version=current.evidence_contract_version,
                    comparable_pair=False,
                    reason_code="recurring_observation_timestamp_not_forward",
                )
            )
            previous_by_identity.pop(identity, None)
            continue

        last_seen_at[identity] = current.observed_at
        previous = previous_by_identity.get(identity)
        if previous is None:
            event = _baseline_event(current)
        else:
            event = classify_observation_pair(previous=previous, current=current)
        events.append(event)

        if not current.has_evidence_hash:
            previous_by_identity.pop(identity, None)
        else:
            # A contract boundary is safe as the baseline for the next sighting
            # under the new version; no cross-version unchanged/changed claim is
            # made for the boundary event itself.
            previous_by_identity[identity] = current

    return tuple(events)


def recurring_observation_delta_summary(
    events: Iterable[RecurringObservationDeltaEvidence],
) -> dict[str, object]:
    """Return aggregate/redacted metrics with no semantic or product authority."""

    materialized = tuple(events)
    classification_counts: dict[str, int] = {}
    for event in materialized:
        key = event.classification.value
        classification_counts[key] = classification_counts.get(key, 0) + 1

    comparable = tuple(event for event in materialized if event.comparable_pair)
    unchanged = sum(
        event.classification == RecurringObservationClassification.UNCHANGED
        for event in comparable
    )
    changed = sum(
        event.classification == RecurringObservationClassification.EVIDENCE_CHANGED
        for event in comparable
    )
    return {
        "projection_version": RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION,
        "observation_events": len(materialized),
        "identity_count": len({event.identity_key for event in materialized}),
        "classification_counts": dict(sorted(classification_counts.items())),
        "comparable_pairs": len(comparable),
        "unchanged_pairs": unchanged,
        "changed_pairs": changed,
        "unchanged_fraction": (unchanged / len(comparable) if comparable else None),
        "changed_fraction": (changed / len(comparable) if comparable else None),
        "unchanged_changed_distribution_available": bool(comparable),
        "provider_requests": 0,
        "llm_requests": 0,
        "database_writes": 0,
        "product_writes": 0,
        "provider_model_eligible": False,
        "product_authority": False,
    }


__all__ = [
    "RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION",
    "RecurringObservationClassification",
    "RecurringObservationDeltaEvidence",
    "RecurringObservationSnapshot",
    "classify_observation_pair",
    "project_recurring_observation_deltas",
    "recurring_observation_delta_summary",
]
