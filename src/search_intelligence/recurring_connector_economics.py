"""Provider-free recurring-connector delta and economics contract for LLM-BOOST-001.

The recurring connector surface has a stricter economic boundary than one-time
source discovery: unchanged evidence must never trigger a provider or model
request. This module therefore owns only pure normalization, cache/delta
classification, booster-plan eligibility and in-memory economics accounting.
It performs no network, database, lifecycle, ranking, application or product
write.

Field selection for ``normalized_evidence_hash`` remains caller authority. The
caller must pass only durable evidence fields and exclude transport timestamps,
request IDs or other volatile metadata that should not invalidate the semantic
cache.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from enum import StrEnum
import hashlib
import json
import math
import re
import unicodedata

from src.search_intelligence.llm_booster_policy import (
    BOOSTER_CONTRACT_VERSION,
    BoosterPlan,
    BoosterStage,
    BoosterSurface,
    TavilyState,
    build_booster_plan,
    recurring_evidence_fingerprint,
)

_WHITESPACE_RE = re.compile(r"\s+")


class RecurringDeterministicOutcome(StrEnum):
    """Outcome of the mandatory deterministic parse for the current evidence."""

    NOT_RUN = "not_run"
    SUPPORTED = "supported"
    UNRESOLVED = "unresolved"


class RecurringGapKind(StrEnum):
    """Only explicit unresolved families may become semantic-booster candidates."""

    NONE = "none"
    EXTERNAL_INFORMATION = "external_information_gap"
    SEMANTIC_AMBIGUITY = "semantic_ambiguity"
    STRUCTURAL_DRIFT = "structural_drift"


class RecurringDeltaKind(StrEnum):
    NEW = "new"
    UNCHANGED = "unchanged"
    EVIDENCE_CHANGED = "evidence_changed"
    CONTRACT_CHANGED = "contract_changed"
    CACHE_IDENTITY_MISMATCH = "cache_identity_mismatch"


def _normalized_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", unicodedata.normalize("NFC", value).strip())


def _canonical_evidence_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("recurring evidence cannot contain non-finite floats")
        return value
    if isinstance(value, str):
        return _normalized_text(value)
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, nested in value.items():
            if not isinstance(key, str):
                raise TypeError("recurring evidence mapping keys must be strings")
            normalized[_normalized_text(key)] = _canonical_evidence_value(nested)
        return {key: normalized[key] for key in sorted(normalized)}
    if isinstance(value, (list, tuple)):
        return [_canonical_evidence_value(item) for item in value]
    raise TypeError(
        "recurring evidence must contain only JSON-compatible scalar, mapping "
        "or sequence values"
    )


def normalized_evidence_hash(evidence: Mapping[str, object]) -> str:
    """Hash caller-selected durable evidence after conservative normalization."""

    canonical = _canonical_evidence_value(evidence)
    payload = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def source_local_job_identity(
    *,
    external_job_id: str | None,
    source_url: str | None,
) -> str:
    """Return the canonical source-local identity used by the recurring cache."""

    if external_job_id is not None and external_job_id.strip():
        return f"external_id:{external_job_id.strip()}"
    if source_url is not None and source_url.strip():
        return f"source_url:{source_url.strip()}"
    raise ValueError("recurring connector evidence requires external_job_id or source_url")


@dataclass(frozen=True)
class RecurringEvidenceRecord:
    connector_id: str
    source_job_identity: str
    normalized_evidence_hash: str
    contract_version: str
    fingerprint: str
    deterministic_outcome: RecurringDeterministicOutcome

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["deterministic_outcome"] = self.deterministic_outcome.value
        return payload


def build_recurring_evidence_record(
    *,
    connector_id: str,
    external_job_id: str | None,
    source_url: str | None,
    evidence: Mapping[str, object],
    deterministic_outcome: RecurringDeterministicOutcome,
    contract_version: str = BOOSTER_CONTRACT_VERSION,
) -> RecurringEvidenceRecord:
    connector = connector_id.strip()
    version = contract_version.strip()
    if not connector:
        raise ValueError("connector_id must be non-empty")
    if not version:
        raise ValueError("contract_version must be non-empty")

    identity = source_local_job_identity(
        external_job_id=external_job_id,
        source_url=source_url,
    )
    evidence_hash = normalized_evidence_hash(evidence)
    fingerprint = recurring_evidence_fingerprint(
        connector_id=connector,
        source_job_identity=identity,
        normalized_evidence_hash=evidence_hash,
        contract_version=version,
    )
    return RecurringEvidenceRecord(
        connector_id=connector,
        source_job_identity=identity,
        normalized_evidence_hash=evidence_hash,
        contract_version=version,
        fingerprint=fingerprint,
        deterministic_outcome=deterministic_outcome,
    )


def classify_recurring_delta(
    *,
    current: RecurringEvidenceRecord,
    previous: RecurringEvidenceRecord | None,
) -> RecurringDeltaKind:
    if previous is None:
        return RecurringDeltaKind.NEW
    if (
        previous.connector_id != current.connector_id
        or previous.source_job_identity != current.source_job_identity
    ):
        return RecurringDeltaKind.CACHE_IDENTITY_MISMATCH
    if previous.fingerprint == current.fingerprint:
        return RecurringDeltaKind.UNCHANGED
    if previous.contract_version != current.contract_version:
        return RecurringDeltaKind.CONTRACT_CHANGED
    if previous.normalized_evidence_hash != current.normalized_evidence_hash:
        return RecurringDeltaKind.EVIDENCE_CHANGED
    raise AssertionError("recurring fingerprint changed without a classified component change")


@dataclass(frozen=True)
class RecurringConnectorDecision:
    fingerprint: str
    delta_kind: RecurringDeltaKind
    gap_kind: RecurringGapKind
    reason_code: str
    booster_eligible: bool
    booster_plan: BoosterPlan | None
    provider_requests: int = 0
    llm_requests: int = 0
    database_requests: int = 0
    product_writes: int = 0
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "fingerprint": self.fingerprint,
            "delta_kind": self.delta_kind.value,
            "gap_kind": self.gap_kind.value,
            "reason_code": self.reason_code,
            "booster_eligible": self.booster_eligible,
            "booster_plan": self.booster_plan.to_json() if self.booster_plan else None,
            "provider_requests": self.provider_requests,
            "llm_requests": self.llm_requests,
            "database_requests": self.database_requests,
            "product_writes": self.product_writes,
            "product_authority": self.product_authority,
        }


def build_recurring_connector_decision_for_delta(
    *,
    current: RecurringEvidenceRecord,
    delta_kind: RecurringDeltaKind,
    gap_kind: RecurringGapKind,
    tavily_state: TavilyState,
) -> RecurringConnectorDecision:
    """Plan economics for an already-authoritative recurring delta.

    This entry point exists for execution-aware observation projection, whose
    persisted pair truth is authoritative and must not be reconstructed by
    fabricating an in-memory previous cache record. It performs no external
    stage and retains all existing deterministic-first and zero-spend gates.
    """

    if delta_kind == RecurringDeltaKind.CACHE_IDENTITY_MISMATCH:
        return RecurringConnectorDecision(
            fingerprint=current.fingerprint,
            delta_kind=delta_kind,
            gap_kind=gap_kind,
            reason_code="recurring_cache_identity_mismatch",
            booster_eligible=False,
            booster_plan=None,
        )

    if delta_kind == RecurringDeltaKind.UNCHANGED:
        plan = build_booster_plan(
            surface=BoosterSurface.RECURRING_CONNECTOR,
            tavily_state=tavily_state,
            recurring_unchanged_fingerprint=True,
            external_information_gap=(gap_kind == RecurringGapKind.EXTERNAL_INFORMATION),
        )
        return RecurringConnectorDecision(
            fingerprint=current.fingerprint,
            delta_kind=delta_kind,
            gap_kind=gap_kind,
            reason_code="unchanged_recurring_evidence_fingerprint",
            booster_eligible=False,
            booster_plan=plan,
        )

    if current.deterministic_outcome == RecurringDeterministicOutcome.NOT_RUN:
        return RecurringConnectorDecision(
            fingerprint=current.fingerprint,
            delta_kind=delta_kind,
            gap_kind=gap_kind,
            reason_code="deterministic_parse_required_before_booster",
            booster_eligible=False,
            booster_plan=None,
        )

    if current.deterministic_outcome == RecurringDeterministicOutcome.SUPPORTED:
        plan = build_booster_plan(
            surface=BoosterSurface.RECURRING_CONNECTOR,
            tavily_state=tavily_state,
            deterministic_resolved=True,
            external_information_gap=(gap_kind == RecurringGapKind.EXTERNAL_INFORMATION),
        )
        return RecurringConnectorDecision(
            fingerprint=current.fingerprint,
            delta_kind=delta_kind,
            gap_kind=gap_kind,
            reason_code="deterministic_recurring_evidence_supported",
            booster_eligible=False,
            booster_plan=plan,
        )

    if gap_kind == RecurringGapKind.NONE:
        return RecurringConnectorDecision(
            fingerprint=current.fingerprint,
            delta_kind=delta_kind,
            gap_kind=gap_kind,
            reason_code="unclassified_recurring_unresolved",
            booster_eligible=False,
            booster_plan=None,
        )

    plan = build_booster_plan(
        surface=BoosterSurface.RECURRING_CONNECTOR,
        tavily_state=tavily_state,
        deterministic_resolved=False,
        external_information_gap=(gap_kind == RecurringGapKind.EXTERNAL_INFORMATION),
        recurring_unchanged_fingerprint=False,
    )
    return RecurringConnectorDecision(
        fingerprint=current.fingerprint,
        delta_kind=delta_kind,
        gap_kind=gap_kind,
        reason_code=f"recurring_{gap_kind.value}_eligible_after_{delta_kind.value}",
        booster_eligible=True,
        booster_plan=plan,
    )


def build_recurring_connector_decision(
    *,
    current: RecurringEvidenceRecord,
    previous: RecurringEvidenceRecord | None,
    gap_kind: RecurringGapKind,
    tavily_state: TavilyState,
) -> RecurringConnectorDecision:
    """Classify one recurring case without performing any external stage."""

    delta = classify_recurring_delta(current=current, previous=previous)
    return build_recurring_connector_decision_for_delta(
        current=current,
        delta_kind=delta,
        gap_kind=gap_kind,
        tavily_state=tavily_state,
    )


@dataclass(frozen=True)
class OpportunityCostObservation:
    """One provider/model-stage economics observation for later shadow analysis."""

    fingerprint: str
    delta_kind: RecurringDeltaKind
    gap_kind: RecurringGapKind
    stage: BoosterStage
    provider_requests: int = 0
    llm_requests: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    validated_rescue: bool = False
    progressed: bool = False
    product_authority: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not self.fingerprint.strip():
            raise ValueError("opportunity observation fingerprint must be non-empty")
        if self.provider_requests < 0 or self.llm_requests < 0:
            raise ValueError("opportunity observation request counts must be non-negative")
        if self.cost_usd < 0:
            raise ValueError("opportunity observation cost must be non-negative")
        if self.latency_ms < 0:
            raise ValueError("opportunity observation latency must be non-negative")
        if self.delta_kind == RecurringDeltaKind.UNCHANGED and (
            self.provider_requests != 0
            or self.llm_requests != 0
            or self.cost_usd != 0.0
        ):
            raise ValueError(
                "unchanged recurring evidence cannot record provider/model spend"
            )


class RecurringOpportunityCostLedger:
    """Pure in-memory ledger for shadow/canary economics evidence."""

    def __init__(self) -> None:
        self._observations: dict[tuple[str, BoosterStage], OpportunityCostObservation] = {}
        self._duplicate_observations_suppressed = 0

    def record(self, observation: OpportunityCostObservation) -> bool:
        key = (observation.fingerprint, observation.stage)
        if key in self._observations:
            self._duplicate_observations_suppressed += 1
            return False
        self._observations[key] = observation
        return True

    def contains(self, *, fingerprint: str, stage: BoosterStage) -> bool:
        return (fingerprint, stage) in self._observations

    def summary(self) -> dict[str, object]:
        observations = tuple(self._observations.values())
        total_cost = sum(item.cost_usd for item in observations)
        validated_rescues = sum(1 for item in observations if item.validated_rescue)
        per_stage: dict[str, int] = {}
        for item in observations:
            per_stage[item.stage.value] = per_stage.get(item.stage.value, 0) + 1
        return {
            "observation_count": len(observations),
            "unique_fingerprints": len({item.fingerprint for item in observations}),
            "provider_requests": sum(item.provider_requests for item in observations),
            "llm_requests": sum(item.llm_requests for item in observations),
            "total_cost_usd": round(total_cost, 8),
            "total_latency_ms": sum(item.latency_ms for item in observations),
            "validated_rescues": validated_rescues,
            "cost_per_validated_rescue_usd": (
                round(total_cost / validated_rescues, 8)
                if validated_rescues
                else None
            ),
            "stage_observations": dict(sorted(per_stage.items())),
            "duplicate_observations_suppressed": self._duplicate_observations_suppressed,
            "product_authority": False,
        }
