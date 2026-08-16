"""Pure deterministic classification for observation-bound recurring evidence.

This module bridges persisted post-097 observation evidence into the already
sealed recurring economics contract. It deliberately reuses the existing
Silver transformer as the structural parse authority instead of creating a
parallel connector parser.

It performs no network, provider, model, database or product operation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass

from src.ingestion.recurring_observation_evidence import (
    RECURRING_OBSERVATION_EVIDENCE_CONTRACT_VERSION,
)
from src.search_intelligence.recurring_connector_economics import (
    RecurringDeterministicOutcome,
    RecurringGapKind,
    normalized_evidence_hash,
)
from src.silver.transformer import transform_raw_job_to_silver


@dataclass(frozen=True)
class RecurringDeterministicClassification:
    """Provider-free classification of one exact current observation."""

    deterministic_outcome: RecurringDeterministicOutcome
    gap_kind: RecurringGapKind
    reason_code: str
    source_url_present: bool
    title_present: bool
    company_name_present: bool
    evidence_hash_bound: bool
    evidence_contract_bound: bool
    provider_requests: int = 0
    llm_requests: int = 0
    database_requests: int = 0
    product_writes: int = 0
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["deterministic_outcome"] = self.deterministic_outcome.value
        payload["gap_kind"] = self.gap_kind.value
        return payload


def _unresolved(
    reason_code: str,
    *,
    source_url_present: bool = False,
    title_present: bool = False,
    company_name_present: bool = False,
    evidence_hash_bound: bool = False,
    evidence_contract_bound: bool = False,
) -> RecurringDeterministicClassification:
    return RecurringDeterministicClassification(
        deterministic_outcome=RecurringDeterministicOutcome.UNRESOLVED,
        gap_kind=RecurringGapKind.STRUCTURAL_DRIFT,
        reason_code=reason_code,
        source_url_present=source_url_present,
        title_present=title_present,
        company_name_present=company_name_present,
        evidence_hash_bound=evidence_hash_bound,
        evidence_contract_bound=evidence_contract_bound,
    )


def _present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def classify_recurring_observation_evidence(
    *,
    source_name: str,
    external_job_id: str | None,
    normalized_evidence: Mapping[str, object] | None,
    persisted_evidence_hash: str | None,
    evidence_contract_version: str | None,
) -> RecurringDeterministicClassification:
    """Classify one persisted current observation without external side effects.

    ``SUPPORTED`` means only that the exact current observation can be understood
    by the repository's existing deterministic Silver structural parser and
    yields the minimal canonical identity-bearing fields used by that path.
    It does not imply product relevance, ranking or application authority.

    Any malformed/unsupported shape fails closed to ``UNRESOLVED`` with the only
    mechanically justified gap family, ``structural_drift``. Semantic ambiguity
    and external-information gaps require separate evidence and are never
    inferred here.
    """

    if not isinstance(normalized_evidence, Mapping):
        return _unresolved("observation_evidence_missing_or_malformed")

    contract_bound = (
        evidence_contract_version == RECURRING_OBSERVATION_EVIDENCE_CONTRACT_VERSION
    )
    if not contract_bound:
        return _unresolved(
            "observation_evidence_contract_mismatch",
            evidence_contract_bound=False,
        )

    if not isinstance(persisted_evidence_hash, str) or not persisted_evidence_hash.strip():
        return _unresolved(
            "observation_evidence_hash_missing",
            evidence_contract_bound=True,
        )

    try:
        computed_hash = normalized_evidence_hash(normalized_evidence)
    except (TypeError, ValueError):
        return _unresolved(
            "observation_evidence_not_hashable",
            evidence_contract_bound=True,
        )

    hash_bound = computed_hash == persisted_evidence_hash
    if not hash_bound:
        return _unresolved(
            "observation_evidence_hash_mismatch",
            evidence_hash_bound=False,
            evidence_contract_bound=True,
        )

    source_url = normalized_evidence.get("source_url")
    raw_evidence = normalized_evidence.get("raw_evidence")
    source_url_present = _present(source_url)
    if not source_url_present or not isinstance(raw_evidence, Mapping):
        return _unresolved(
            "observation_evidence_projection_shape_invalid",
            source_url_present=source_url_present,
            evidence_hash_bound=True,
            evidence_contract_bound=True,
        )

    raw_job = {
        "id": 0,
        "source_name": source_name,
        "external_job_id": external_job_id,
        "source_url": str(source_url).strip(),
        "raw_data": dict(raw_evidence),
    }

    try:
        silver = transform_raw_job_to_silver(raw_job)
    except (KeyError, TypeError, ValueError):
        return _unresolved(
            "deterministic_silver_transform_unsupported",
            source_url_present=True,
            evidence_hash_bound=True,
            evidence_contract_bound=True,
        )

    projected_source_url = silver.get("source_url")
    title = silver.get("title")
    company_name = silver.get("company_name")
    projected_source_url_present = _present(projected_source_url)
    title_present = _present(title)
    company_name_present = _present(company_name)

    if not (projected_source_url_present and title_present and company_name_present):
        return _unresolved(
            "deterministic_silver_core_fields_incomplete",
            source_url_present=projected_source_url_present,
            title_present=title_present,
            company_name_present=company_name_present,
            evidence_hash_bound=True,
            evidence_contract_bound=True,
        )

    return RecurringDeterministicClassification(
        deterministic_outcome=RecurringDeterministicOutcome.SUPPORTED,
        gap_kind=RecurringGapKind.NONE,
        reason_code="deterministic_silver_structure_supported",
        source_url_present=True,
        title_present=True,
        company_name_present=True,
        evidence_hash_bound=True,
        evidence_contract_bound=True,
    )
