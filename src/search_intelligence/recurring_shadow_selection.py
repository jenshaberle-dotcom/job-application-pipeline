"""Pure shadow-candidate selection for recurring connector evidence.

The execution-aware observation projection owns pair truth. The recurring
connector economics contract owns deterministic-first booster planning. This
module joins those two pure contracts without performing a provider, model,
network, database or product operation.

A truthful cross-execution evidence change is necessary but not sufficient for
shadow eligibility: the current deterministic parse must also be unresolved and
an explicit recurring gap family must exist. Baselines, unchanged evidence,
contract boundaries and every fail-closed projection state remain shadow
ineligible.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from src.search_intelligence.llm_booster_policy import TavilyState
from src.search_intelligence.recurring_connector_economics import (
    RecurringConnectorDecision,
    RecurringDeltaKind,
    RecurringEvidenceRecord,
    RecurringGapKind,
    build_recurring_connector_decision_for_delta,
)
from src.search_intelligence.recurring_observation_delta_projection import (
    RecurringObservationClassification,
    RecurringObservationDeltaEvidence,
)


@dataclass(frozen=True)
class RecurringShadowSelection:
    """Product-neutral decision about later shadow-sample candidacy."""

    identity_key: str
    projection_classification: RecurringObservationClassification
    projection_reason_code: str
    shadow_sample_eligible: bool
    reason_code: str
    economics_decision: RecurringConnectorDecision | None
    provider_requests: int = 0
    llm_requests: int = 0
    database_requests: int = 0
    product_writes: int = 0
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["projection_classification"] = self.projection_classification.value
        payload["economics_decision"] = (
            self.economics_decision.to_json() if self.economics_decision else None
        )
        return payload


def _selection(
    *,
    projection: RecurringObservationDeltaEvidence,
    eligible: bool,
    reason_code: str,
    economics_decision: RecurringConnectorDecision | None = None,
) -> RecurringShadowSelection:
    return RecurringShadowSelection(
        identity_key=projection.identity_key,
        projection_classification=projection.classification,
        projection_reason_code=projection.reason_code,
        shadow_sample_eligible=eligible,
        reason_code=reason_code,
        economics_decision=economics_decision,
    )


def _projection_identity_for(current: RecurringEvidenceRecord) -> str:
    return f"{current.connector_id}|{current.source_job_identity}"


def select_recurring_shadow_candidate(
    *,
    projection: RecurringObservationDeltaEvidence,
    current: RecurringEvidenceRecord,
    gap_kind: RecurringGapKind,
    tavily_state: TavilyState,
) -> RecurringShadowSelection:
    """Join authoritative pair truth to canonical recurring booster economics.

    The selector never runs the planned stages. It only answers whether a later
    shadow sampler may consider the case, while retaining zero product authority.
    """

    if projection.provider_model_eligible or projection.product_authority:
        return _selection(
            projection=projection,
            eligible=False,
            reason_code="projection_authority_boundary_violation",
        )

    expected_identity = _projection_identity_for(current)
    if projection.identity_key != expected_identity:
        return _selection(
            projection=projection,
            eligible=False,
            reason_code="projection_current_identity_mismatch",
        )

    if projection.current_normalized_evidence_hash != current.normalized_evidence_hash:
        return _selection(
            projection=projection,
            eligible=False,
            reason_code="projection_current_evidence_hash_mismatch",
        )

    classification = projection.classification
    delta_kind = projection.delta_kind

    if classification == RecurringObservationClassification.UNCHANGED:
        if (
            not projection.comparable_pair
            or delta_kind != RecurringDeltaKind.UNCHANGED
            or projection.current_execution_id is None
            or projection.previous_execution_id is None
            or projection.current_execution_id == projection.previous_execution_id
        ):
            return _selection(
                projection=projection,
                eligible=False,
                reason_code="projection_unchanged_invariant_failed",
            )
        economics = build_recurring_connector_decision_for_delta(
            current=current,
            delta_kind=RecurringDeltaKind.UNCHANGED,
            gap_kind=gap_kind,
            tavily_state=tavily_state,
        )
        return _selection(
            projection=projection,
            eligible=False,
            reason_code="truthful_recurring_unchanged_zero_spend",
            economics_decision=economics,
        )

    if classification == RecurringObservationClassification.EVIDENCE_CHANGED:
        if (
            not projection.comparable_pair
            or delta_kind != RecurringDeltaKind.EVIDENCE_CHANGED
            or projection.current_execution_id is None
            or projection.previous_execution_id is None
            or projection.current_execution_id == projection.previous_execution_id
        ):
            return _selection(
                projection=projection,
                eligible=False,
                reason_code="projection_evidence_changed_invariant_failed",
            )
        economics = build_recurring_connector_decision_for_delta(
            current=current,
            delta_kind=RecurringDeltaKind.EVIDENCE_CHANGED,
            gap_kind=gap_kind,
            tavily_state=tavily_state,
        )
        return _selection(
            projection=projection,
            eligible=economics.booster_eligible,
            reason_code=(
                "truthful_cross_execution_change_shadow_candidate"
                if economics.booster_eligible
                else f"truthful_change_{economics.reason_code}"
            ),
            economics_decision=economics,
        )

    if projection.comparable_pair:
        return _selection(
            projection=projection,
            eligible=False,
            reason_code="projection_non_delta_marked_comparable",
        )

    return _selection(
        projection=projection,
        eligible=False,
        reason_code=f"projection_{classification.value}_shadow_ineligible",
    )


__all__ = [
    "RecurringShadowSelection",
    "select_recurring_shadow_candidate",
]
