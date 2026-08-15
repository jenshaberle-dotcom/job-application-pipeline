from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from src.search_intelligence.llm_booster_policy import (
    BoosterStage,
    BoosterSurface,
    TavilyState,
)
from src.search_intelligence.recurring_connector_economics import (
    RecurringDeltaKind,
    RecurringDeterministicOutcome,
    RecurringGapKind,
    build_recurring_connector_decision,
    build_recurring_connector_decision_for_delta,
    build_recurring_evidence_record,
    classify_recurring_delta,
)
from src.search_intelligence.recurring_observation_delta_projection import (
    RecurringObservationClassification,
    RecurringObservationSnapshot,
    classify_observation_pair,
    project_recurring_observation_deltas,
)
from src.search_intelligence.recurring_shadow_selection import (
    select_recurring_shadow_candidate,
)

BASE = datetime(2026, 8, 15, 8, 0, tzinfo=UTC)
CONNECTOR = "personio:bridgingit"
JOB_ID = "job-42"
URL = "https://bridgingit.jobs.personio.de/job/42"
OBS_CONTRACT_V1 = "recurring-observation-evidence.v1"
OBS_CONTRACT_V2 = "recurring-observation-evidence.v2"
EXEC_A = "11111111-1111-4111-8111-111111111111"
EXEC_B = "22222222-2222-4222-8222-222222222222"
FALLBACK_HASH_A = "a" * 64
FALLBACK_HASH_B = "b" * 64


def _record(
    outcome: RecurringDeterministicOutcome,
    *,
    evidence: dict[str, object] | None = None,
):
    return build_recurring_evidence_record(
        connector_id=CONNECTOR,
        external_job_id=JOB_ID,
        source_url=URL,
        evidence=evidence or {"title": "Current", "location": "Hannover"},
        deterministic_outcome=outcome,
    )


def _different_hash(current_hash: str) -> str:
    return FALLBACK_HASH_A if current_hash != FALLBACK_HASH_A else FALLBACK_HASH_B


def _snapshot(
    *,
    evidence_hash: str,
    minutes: int,
    execution_id: str | None,
    contract: str = OBS_CONTRACT_V1,
    source_name: str = CONNECTOR,
) -> RecurringObservationSnapshot:
    return RecurringObservationSnapshot(
        source_name=source_name,
        external_job_id=JOB_ID,
        source_url=URL,
        observed_at=BASE + timedelta(minutes=minutes),
        normalized_evidence_hash=evidence_hash,
        evidence_contract_version=contract,
        execution_id=execution_id,
    )


def _changed_projection(current_hash: str):
    return project_recurring_observation_deltas(
        [
            _snapshot(
                evidence_hash=_different_hash(current_hash),
                minutes=0,
                execution_id=EXEC_A,
            ),
            _snapshot(
                evidence_hash=current_hash,
                minutes=1,
                execution_id=EXEC_B,
            ),
        ]
    )[-1]


def _unchanged_projection(current_hash: str):
    return project_recurring_observation_deltas(
        [
            _snapshot(
                evidence_hash=current_hash,
                minutes=0,
                execution_id=EXEC_A,
            ),
            _snapshot(
                evidence_hash=current_hash,
                minutes=1,
                execution_id=EXEC_B,
            ),
        ]
    )[-1]


def test_baseline_is_never_shadow_candidate() -> None:
    current = _record(RecurringDeterministicOutcome.UNRESOLVED)
    projection = project_recurring_observation_deltas(
        [
            _snapshot(
                evidence_hash=current.normalized_evidence_hash,
                minutes=0,
                execution_id=EXEC_A,
            )
        ]
    )[0]

    selection = select_recurring_shadow_candidate(
        projection=projection,
        current=current,
        gap_kind=RecurringGapKind.SEMANTIC_AMBIGUITY,
        tavily_state=TavilyState.DISABLED,
    )

    assert projection.classification == RecurringObservationClassification.BASELINE_ONLY
    assert selection.shadow_sample_eligible is False
    assert selection.economics_decision is None
    assert selection.reason_code == "projection_baseline_only_shadow_ineligible"


def test_missing_execution_is_never_inferred_for_shadow() -> None:
    current = _record(RecurringDeterministicOutcome.UNRESOLVED)
    projection = project_recurring_observation_deltas(
        [
            _snapshot(
                evidence_hash=current.normalized_evidence_hash,
                minutes=0,
                execution_id=None,
            )
        ]
    )[0]

    selection = select_recurring_shadow_candidate(
        projection=projection,
        current=current,
        gap_kind=RecurringGapKind.STRUCTURAL_DRIFT,
        tavily_state=TavilyState.DISABLED,
    )

    assert projection.classification == (
        RecurringObservationClassification.INCOMPARABLE_MISSING_EXECUTION
    )
    assert selection.shadow_sample_eligible is False
    assert selection.economics_decision is None


def test_same_execution_duplicate_and_conflict_are_shadow_ineligible() -> None:
    current = _record(RecurringDeterministicOutcome.UNRESOLVED)
    previous = _snapshot(
        evidence_hash=current.normalized_evidence_hash,
        minutes=0,
        execution_id=EXEC_A,
    )
    duplicate = classify_observation_pair(
        previous=previous,
        current=_snapshot(
            evidence_hash=current.normalized_evidence_hash,
            minutes=1,
            execution_id=EXEC_A,
        ),
    )
    conflict = classify_observation_pair(
        previous=previous,
        current=_snapshot(
            evidence_hash=_different_hash(current.normalized_evidence_hash),
            minutes=1,
            execution_id=EXEC_A,
        ),
    )

    duplicate_selection = select_recurring_shadow_candidate(
        projection=duplicate,
        current=current,
        gap_kind=RecurringGapKind.SEMANTIC_AMBIGUITY,
        tavily_state=TavilyState.DISABLED,
    )
    assert duplicate.classification == (
        RecurringObservationClassification.SAME_EXECUTION_DUPLICATE
    )
    assert duplicate_selection.shadow_sample_eligible is False

    conflict_current = _record(
        RecurringDeterministicOutcome.UNRESOLVED,
        evidence={"title": "Conflict current", "location": "Hannover"},
    )
    conflict = replace(
        conflict,
        current_normalized_evidence_hash=conflict_current.normalized_evidence_hash,
    )
    conflict_selection = select_recurring_shadow_candidate(
        projection=conflict,
        current=conflict_current,
        gap_kind=RecurringGapKind.STRUCTURAL_DRIFT,
        tavily_state=TavilyState.DISABLED,
    )
    assert conflict.classification == RecurringObservationClassification.SAME_EXECUTION_CONFLICT
    assert conflict_selection.shadow_sample_eligible is False


def test_contract_boundary_is_not_evidence_change_shadow_candidate() -> None:
    current = _record(RecurringDeterministicOutcome.UNRESOLVED)
    projection = project_recurring_observation_deltas(
        [
            _snapshot(
                evidence_hash=current.normalized_evidence_hash,
                minutes=0,
                execution_id=EXEC_A,
                contract=OBS_CONTRACT_V1,
            ),
            _snapshot(
                evidence_hash=current.normalized_evidence_hash,
                minutes=1,
                execution_id=EXEC_B,
                contract=OBS_CONTRACT_V2,
            ),
        ]
    )[-1]

    selection = select_recurring_shadow_candidate(
        projection=projection,
        current=current,
        gap_kind=RecurringGapKind.EXTERNAL_INFORMATION,
        tavily_state=TavilyState.AVAILABLE,
    )

    assert projection.classification == RecurringObservationClassification.CONTRACT_BOUNDARY
    assert projection.delta_kind == RecurringDeltaKind.CONTRACT_CHANGED
    assert selection.shadow_sample_eligible is False
    assert selection.economics_decision is None


def test_truthful_unchanged_flows_only_to_zero_spend_economics() -> None:
    current = _record(RecurringDeterministicOutcome.UNRESOLVED)
    projection = _unchanged_projection(current.normalized_evidence_hash)

    selection = select_recurring_shadow_candidate(
        projection=projection,
        current=current,
        gap_kind=RecurringGapKind.EXTERNAL_INFORMATION,
        tavily_state=TavilyState.AVAILABLE,
    )

    assert projection.comparable_pair is True
    assert projection.delta_kind == RecurringDeltaKind.UNCHANGED
    assert selection.shadow_sample_eligible is False
    assert selection.reason_code == "truthful_recurring_unchanged_zero_spend"
    assert selection.economics_decision is not None
    assert selection.economics_decision.booster_eligible is False
    assert selection.economics_decision.booster_plan is not None
    assert selection.economics_decision.booster_plan.recurring_unchanged_fingerprint is True
    assert all(
        not stage.eligible
        for stage in selection.economics_decision.booster_plan.stages
        if stage.stage != BoosterStage.DETERMINISTIC
    )


@pytest.mark.parametrize(
    ("outcome", "gap", "reason_fragment"),
    [
        (
            RecurringDeterministicOutcome.NOT_RUN,
            RecurringGapKind.SEMANTIC_AMBIGUITY,
            "deterministic_parse_required_before_booster",
        ),
        (
            RecurringDeterministicOutcome.SUPPORTED,
            RecurringGapKind.SEMANTIC_AMBIGUITY,
            "deterministic_recurring_evidence_supported",
        ),
        (
            RecurringDeterministicOutcome.UNRESOLVED,
            RecurringGapKind.NONE,
            "unclassified_recurring_unresolved",
        ),
    ],
)
def test_truthful_changed_still_requires_deterministic_gap_eligibility(
    outcome: RecurringDeterministicOutcome,
    gap: RecurringGapKind,
    reason_fragment: str,
) -> None:
    current = _record(outcome)
    projection = _changed_projection(current.normalized_evidence_hash)

    selection = select_recurring_shadow_candidate(
        projection=projection,
        current=current,
        gap_kind=gap,
        tavily_state=TavilyState.DISABLED,
    )

    assert projection.classification == RecurringObservationClassification.EVIDENCE_CHANGED
    assert projection.comparable_pair is True
    assert selection.shadow_sample_eligible is False
    assert selection.economics_decision is not None
    assert selection.economics_decision.booster_eligible is False
    assert reason_fragment in selection.reason_code


@pytest.mark.parametrize(
    "gap",
    [
        RecurringGapKind.SEMANTIC_AMBIGUITY,
        RecurringGapKind.STRUCTURAL_DRIFT,
    ],
)
def test_truthful_changed_unresolved_semantic_gap_can_be_shadow_candidate(
    gap: RecurringGapKind,
) -> None:
    current = _record(RecurringDeterministicOutcome.UNRESOLVED)
    projection = _changed_projection(current.normalized_evidence_hash)

    selection = select_recurring_shadow_candidate(
        projection=projection,
        current=current,
        gap_kind=gap,
        tavily_state=TavilyState.DISABLED,
    )

    assert selection.shadow_sample_eligible is True
    assert selection.reason_code == "truthful_cross_execution_change_shadow_candidate"
    assert selection.economics_decision is not None
    assert selection.economics_decision.booster_eligible is True
    assert selection.economics_decision.booster_plan is not None
    assert selection.economics_decision.booster_plan.surface == BoosterSurface.RECURRING_CONNECTOR


def test_external_information_gap_uses_canonical_tavily_planning_without_running_it() -> None:
    current = _record(RecurringDeterministicOutcome.UNRESOLVED)
    projection = _changed_projection(current.normalized_evidence_hash)

    selection = select_recurring_shadow_candidate(
        projection=projection,
        current=current,
        gap_kind=RecurringGapKind.EXTERNAL_INFORMATION,
        tavily_state=TavilyState.AVAILABLE,
    )

    assert selection.shadow_sample_eligible is True
    assert selection.economics_decision is not None
    plan = selection.economics_decision.booster_plan
    assert plan is not None
    tavily = next(stage for stage in plan.stages if stage.stage == BoosterStage.TAVILY)
    assert tavily.eligible is True
    assert plan.provider_network_requests == 0
    assert plan.llm_requests == 0
    assert selection.provider_requests == 0
    assert selection.llm_requests == 0
    assert selection.database_requests == 0
    assert selection.product_writes == 0
    assert selection.product_authority is False


def test_projection_identity_and_hash_must_match_current_economics_record() -> None:
    current = _record(RecurringDeterministicOutcome.UNRESOLVED)
    projection = _changed_projection(current.normalized_evidence_hash)

    identity_mismatch = select_recurring_shadow_candidate(
        projection=replace(projection, identity_key="personio:lookalike|external_id:job-42"),
        current=current,
        gap_kind=RecurringGapKind.SEMANTIC_AMBIGUITY,
        tavily_state=TavilyState.DISABLED,
    )
    hash_mismatch = select_recurring_shadow_candidate(
        projection=replace(
            projection,
            current_normalized_evidence_hash=_different_hash(current.normalized_evidence_hash),
        ),
        current=current,
        gap_kind=RecurringGapKind.SEMANTIC_AMBIGUITY,
        tavily_state=TavilyState.DISABLED,
    )

    assert identity_mismatch.shadow_sample_eligible is False
    assert identity_mismatch.reason_code == "projection_current_identity_mismatch"
    assert hash_mismatch.shadow_sample_eligible is False
    assert hash_mismatch.reason_code == "projection_current_evidence_hash_mismatch"


def test_projection_classification_delta_inconsistency_fails_closed() -> None:
    current = _record(RecurringDeterministicOutcome.UNRESOLVED)
    changed = _changed_projection(current.normalized_evidence_hash)

    inconsistent = replace(changed, delta_kind=RecurringDeltaKind.UNCHANGED)
    selection = select_recurring_shadow_candidate(
        projection=inconsistent,
        current=current,
        gap_kind=RecurringGapKind.SEMANTIC_AMBIGUITY,
        tavily_state=TavilyState.DISABLED,
    )

    assert selection.shadow_sample_eligible is False
    assert selection.reason_code == "projection_evidence_changed_invariant_failed"
    assert selection.economics_decision is None


def test_authoritative_delta_helper_preserves_existing_economics_behavior() -> None:
    previous = _record(
        RecurringDeterministicOutcome.UNRESOLVED,
        evidence={"title": "Previous", "location": "Hannover"},
    )
    current = _record(
        RecurringDeterministicOutcome.UNRESOLVED,
        evidence={"title": "Current", "location": "Hannover"},
    )
    delta = classify_recurring_delta(current=current, previous=previous)
    assert delta == RecurringDeltaKind.EVIDENCE_CHANGED

    legacy = build_recurring_connector_decision(
        current=current,
        previous=previous,
        gap_kind=RecurringGapKind.SEMANTIC_AMBIGUITY,
        tavily_state=TavilyState.DISABLED,
    )
    authoritative = build_recurring_connector_decision_for_delta(
        current=current,
        delta_kind=delta,
        gap_kind=RecurringGapKind.SEMANTIC_AMBIGUITY,
        tavily_state=TavilyState.DISABLED,
    )

    assert authoritative.to_json() == legacy.to_json()
