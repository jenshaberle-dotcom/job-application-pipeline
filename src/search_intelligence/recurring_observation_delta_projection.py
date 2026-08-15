"""Pure execution-aware post-095 recurring-observation delta projection.

This module bridges already-read ``job_observations`` metadata plus the joined
``ingestion_runs.execution_id`` into truthful recurring delta evidence. It does
not query a database or grant provider/model/product authority.

The comparison unit is one exact source-local job identity observed in one
canonical ingestion execution. Multiple profile/search-term sightings inside the
same ``src.ingest_jobs`` invocation never count as recurrence. Only distinct,
non-overlapping, fully evidenced executions may form an unchanged/changed pair.
Historical rows without execution correlation remain incomparable; no timestamp
heuristic, synthesis or backfill is permitted here.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
import re
from uuid import UUID

from src.search_intelligence.recurring_connector_economics import (
    RecurringDeltaKind,
    source_local_job_identity,
)

RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION = (
    "LLM-BOOST-001.recurring-observation-delta-projection.v3"
)
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class RecurringObservationClassification(StrEnum):
    """Truth status for one execution-level observation event."""

    BASELINE_ONLY = "baseline_only"
    UNCHANGED = "unchanged"
    EVIDENCE_CHANGED = "evidence_changed"
    CONTRACT_BOUNDARY = "contract_boundary"
    INCOMPARABLE_MISSING_EVIDENCE = "incomparable_missing_evidence"
    INCOMPARABLE_MISSING_EXECUTION = "incomparable_missing_execution"
    SAME_EXECUTION_DUPLICATE = "same_execution_duplicate"
    SAME_EXECUTION_CONFLICT = "same_execution_conflict"
    EXECUTION_REENTRY = "execution_reentry"
    IDENTITY_MISMATCH = "identity_mismatch"
    NON_FORWARD_TIMESTAMP = "non_forward_timestamp"


@dataclass(frozen=True)
class RecurringObservationSnapshot:
    """Minimal persisted metadata required for truthful recurring comparison."""

    source_name: str
    external_job_id: str | None
    source_url: str | None
    observed_at: datetime
    normalized_evidence_hash: str | None
    evidence_contract_version: str | None
    execution_id: str | None

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

        if self.execution_id is not None:
            execution = self.execution_id.strip()
            if not execution:
                raise ValueError("execution_id must be non-empty when present")
            try:
                UUID(execution)
            except ValueError as exc:
                raise ValueError("execution_id must be a UUID when present") from exc

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

        raw_execution_id = row.get("execution_id")
        if raw_execution_id is None:
            execution_id = None
        elif isinstance(raw_execution_id, (str, UUID)):
            execution_id = str(raw_execution_id)
        else:
            raise TypeError("execution_id must be a UUID/string or null")

        return cls(
            source_name=source_name,
            external_job_id=optional_text("external_job_id"),
            source_url=optional_text("source_url"),
            observed_at=observed_at,
            normalized_evidence_hash=optional_text("normalized_evidence_hash"),
            evidence_contract_version=optional_text("evidence_contract_version"),
            execution_id=execution_id,
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
    """One redacted execution-level classification event."""

    projection_version: str
    identity_key: str
    classification: RecurringObservationClassification
    delta_kind: RecurringDeltaKind | None
    current_observed_at: datetime
    previous_observed_at: datetime | None
    current_execution_id: str | None
    previous_execution_id: str | None
    current_normalized_evidence_hash: str | None
    evidence_contract_version: str | None
    comparable_pair: bool
    reason_code: str
    execution_observation_count: int = 1
    same_execution_duplicate_observations: int = 0
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


def _event(
    *,
    current: RecurringObservationSnapshot,
    classification: RecurringObservationClassification,
    delta_kind: RecurringDeltaKind | None,
    comparable_pair: bool,
    reason_code: str,
    previous: RecurringObservationSnapshot | None = None,
    execution_observation_count: int = 1,
    same_execution_duplicate_observations: int = 0,
) -> RecurringObservationDeltaEvidence:
    return RecurringObservationDeltaEvidence(
        projection_version=RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION,
        identity_key=current.identity_key,
        classification=classification,
        delta_kind=delta_kind,
        current_observed_at=current.observed_at,
        previous_observed_at=(previous.observed_at if previous else None),
        current_execution_id=current.execution_id,
        previous_execution_id=(previous.execution_id if previous else None),
        current_normalized_evidence_hash=current.normalized_evidence_hash,
        evidence_contract_version=current.evidence_contract_version,
        comparable_pair=comparable_pair,
        reason_code=reason_code,
        execution_observation_count=execution_observation_count,
        same_execution_duplicate_observations=same_execution_duplicate_observations,
    )


def classify_observation_pair(
    *,
    previous: RecurringObservationSnapshot,
    current: RecurringObservationSnapshot,
) -> RecurringObservationDeltaEvidence:
    """Classify two exact sightings while requiring distinct execution IDs."""

    if previous.identity_key != current.identity_key:
        return _event(
            current=current,
            previous=previous,
            classification=RecurringObservationClassification.IDENTITY_MISMATCH,
            delta_kind=RecurringDeltaKind.CACHE_IDENTITY_MISMATCH,
            comparable_pair=False,
            reason_code="recurring_observation_identity_mismatch",
        )
    if current.observed_at <= previous.observed_at:
        return _event(
            current=current,
            previous=previous,
            classification=RecurringObservationClassification.NON_FORWARD_TIMESTAMP,
            delta_kind=None,
            comparable_pair=False,
            reason_code="recurring_observation_timestamp_not_forward",
        )
    if previous.execution_id is None or current.execution_id is None:
        return _event(
            current=current,
            previous=previous,
            classification=RecurringObservationClassification.INCOMPARABLE_MISSING_EXECUTION,
            delta_kind=None,
            comparable_pair=False,
            reason_code="recurring_observation_execution_correlation_missing",
        )
    if previous.execution_id == current.execution_id:
        same_evidence = (
            previous.normalized_evidence_hash == current.normalized_evidence_hash
            and previous.evidence_contract_version == current.evidence_contract_version
        )
        return _event(
            current=current,
            previous=previous,
            classification=(
                RecurringObservationClassification.SAME_EXECUTION_DUPLICATE
                if same_evidence
                else RecurringObservationClassification.SAME_EXECUTION_CONFLICT
            ),
            delta_kind=None,
            comparable_pair=False,
            reason_code=(
                "recurring_observation_same_execution_duplicate"
                if same_evidence
                else "recurring_observation_same_execution_conflicting_evidence"
            ),
        )
    if not previous.has_evidence_hash or not current.has_evidence_hash:
        return _event(
            current=current,
            previous=previous,
            classification=RecurringObservationClassification.INCOMPARABLE_MISSING_EVIDENCE,
            delta_kind=None,
            comparable_pair=False,
            reason_code="recurring_observation_pair_missing_truthful_hash_history",
        )
    if previous.evidence_contract_version != current.evidence_contract_version:
        return _event(
            current=current,
            previous=previous,
            classification=RecurringObservationClassification.CONTRACT_BOUNDARY,
            delta_kind=RecurringDeltaKind.CONTRACT_CHANGED,
            comparable_pair=False,
            reason_code="recurring_observation_evidence_contract_changed",
        )
    if previous.normalized_evidence_hash == current.normalized_evidence_hash:
        return _event(
            current=current,
            previous=previous,
            classification=RecurringObservationClassification.UNCHANGED,
            delta_kind=RecurringDeltaKind.UNCHANGED,
            comparable_pair=True,
            reason_code="recurring_observation_distinct_execution_hash_unchanged",
        )
    return _event(
        current=current,
        previous=previous,
        classification=RecurringObservationClassification.EVIDENCE_CHANGED,
        delta_kind=RecurringDeltaKind.EVIDENCE_CHANGED,
        comparable_pair=True,
        reason_code="recurring_observation_distinct_execution_hash_changed",
    )


def _finalize_execution_group(
    group: list[RecurringObservationSnapshot],
    previous_baseline: RecurringObservationSnapshot | None,
) -> tuple[RecurringObservationDeltaEvidence, RecurringObservationSnapshot | None]:
    current = group[-1]
    duplicate_count = max(0, len(group) - 1)

    if current.execution_id is None:
        return (
            _event(
                current=current,
                previous=previous_baseline,
                classification=RecurringObservationClassification.INCOMPARABLE_MISSING_EXECUTION,
                delta_kind=None,
                comparable_pair=False,
                reason_code="recurring_observation_execution_correlation_missing",
                execution_observation_count=len(group),
            ),
            None,
        )

    if any(not snapshot.has_evidence_hash for snapshot in group):
        return (
            _event(
                current=current,
                previous=previous_baseline,
                classification=RecurringObservationClassification.INCOMPARABLE_MISSING_EVIDENCE,
                delta_kind=None,
                comparable_pair=False,
                reason_code="recurring_observation_execution_missing_truthful_hash",
                execution_observation_count=len(group),
            ),
            None,
        )

    evidence_pairs = {
        (snapshot.evidence_contract_version, snapshot.normalized_evidence_hash)
        for snapshot in group
    }
    if len(evidence_pairs) != 1:
        return (
            _event(
                current=current,
                previous=previous_baseline,
                classification=RecurringObservationClassification.SAME_EXECUTION_CONFLICT,
                delta_kind=None,
                comparable_pair=False,
                reason_code="recurring_observation_same_execution_conflicting_evidence",
                execution_observation_count=len(group),
            ),
            None,
        )

    if previous_baseline is None:
        return (
            _event(
                current=current,
                classification=RecurringObservationClassification.BASELINE_ONLY,
                delta_kind=RecurringDeltaKind.NEW,
                comparable_pair=False,
                reason_code="first_valid_execution_is_baseline_only",
                execution_observation_count=len(group),
                same_execution_duplicate_observations=duplicate_count,
            ),
            current,
        )

    pair = classify_observation_pair(previous=previous_baseline, current=current)
    pair = RecurringObservationDeltaEvidence(
        **{
            **asdict(pair),
            "execution_observation_count": len(group),
            "same_execution_duplicate_observations": duplicate_count,
        }
    )
    if pair.classification in {
        RecurringObservationClassification.UNCHANGED,
        RecurringObservationClassification.EVIDENCE_CHANGED,
        RecurringObservationClassification.CONTRACT_BOUNDARY,
    }:
        return pair, current
    return pair, None


def project_recurring_observation_deltas(
    observations: Iterable[RecurringObservationSnapshot],
) -> tuple[RecurringObservationDeltaEvidence, ...]:
    """Group exact identities by execution, then classify only distinct executions."""

    events: list[RecurringObservationDeltaEvidence] = []
    active_groups: dict[str, list[RecurringObservationSnapshot]] = {}
    previous_baselines: dict[str, RecurringObservationSnapshot] = {}
    completed_execution_ids: dict[str, set[str]] = {}
    last_seen_at: dict[str, datetime] = {}

    def finalize(identity: str) -> None:
        group = active_groups.pop(identity, None)
        if not group:
            return
        execution_id = group[-1].execution_id
        event, baseline = _finalize_execution_group(
            group,
            previous_baselines.get(identity),
        )
        events.append(event)
        if execution_id is not None:
            completed_execution_ids.setdefault(identity, set()).add(execution_id)
        if baseline is None:
            previous_baselines.pop(identity, None)
        else:
            previous_baselines[identity] = baseline

    for current in observations:
        identity = current.identity_key
        seen_at = last_seen_at.get(identity)
        if seen_at is not None and current.observed_at <= seen_at:
            finalize(identity)
            events.append(
                _event(
                    current=current,
                    previous=previous_baselines.get(identity),
                    classification=RecurringObservationClassification.NON_FORWARD_TIMESTAMP,
                    delta_kind=None,
                    comparable_pair=False,
                    reason_code="recurring_observation_timestamp_not_forward",
                )
            )
            previous_baselines.pop(identity, None)
            active_groups.pop(identity, None)
            last_seen_at[identity] = current.observed_at
            continue
        last_seen_at[identity] = current.observed_at

        if current.execution_id is None:
            finalize(identity)
            events.append(
                _event(
                    current=current,
                    previous=previous_baselines.get(identity),
                    classification=RecurringObservationClassification.INCOMPARABLE_MISSING_EXECUTION,
                    delta_kind=None,
                    comparable_pair=False,
                    reason_code="recurring_observation_execution_correlation_missing",
                )
            )
            previous_baselines.pop(identity, None)
            continue

        active = active_groups.get(identity)
        if active is None:
            if current.execution_id in completed_execution_ids.get(identity, set()):
                events.append(
                    _event(
                        current=current,
                        previous=previous_baselines.get(identity),
                        classification=RecurringObservationClassification.EXECUTION_REENTRY,
                        delta_kind=None,
                        comparable_pair=False,
                        reason_code="recurring_observation_execution_reentered_after_completion",
                    )
                )
                previous_baselines.pop(identity, None)
                continue
            active_groups[identity] = [current]
            continue

        active_execution_id = active[-1].execution_id
        if active_execution_id == current.execution_id:
            active.append(current)
            continue

        finalize(identity)
        if current.execution_id in completed_execution_ids.get(identity, set()):
            events.append(
                _event(
                    current=current,
                    previous=previous_baselines.get(identity),
                    classification=RecurringObservationClassification.EXECUTION_REENTRY,
                    delta_kind=None,
                    comparable_pair=False,
                    reason_code="recurring_observation_execution_reentered_after_completion",
                )
            )
            previous_baselines.pop(identity, None)
            continue
        active_groups[identity] = [current]

    for identity in tuple(active_groups):
        finalize(identity)

    return tuple(events)


def recurring_observation_delta_summary(
    events: Iterable[RecurringObservationDeltaEvidence],
) -> dict[str, object]:
    """Return aggregate/redacted execution-level metrics with zero product authority."""

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
    duplicate_observations = sum(
        event.same_execution_duplicate_observations for event in materialized
    )
    return {
        "projection_version": RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION,
        "execution_events": len(materialized),
        "observation_rows_accounted": sum(
            event.execution_observation_count for event in materialized
        ),
        "identity_count": len({event.identity_key for event in materialized}),
        "classification_counts": dict(sorted(classification_counts.items())),
        "same_execution_duplicate_observations": duplicate_observations,
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
