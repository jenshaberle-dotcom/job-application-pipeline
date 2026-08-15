from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from src.search_intelligence.recurring_connector_economics import RecurringDeltaKind
from src.search_intelligence.recurring_observation_delta_projection import (
    RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION,
    RecurringObservationClassification,
    RecurringObservationSnapshot,
    classify_observation_pair,
    project_recurring_observation_deltas,
    recurring_observation_delta_summary,
)

BASE = datetime(2026, 8, 15, 0, 30, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
CONTRACT_V1 = "recurring-observation-evidence.v1"
CONTRACT_V2 = "recurring-observation-evidence.v2"
EXEC_A = "11111111-1111-4111-8111-111111111111"
EXEC_B = "22222222-2222-4222-8222-222222222222"
EXEC_C = "33333333-3333-4333-8333-333333333333"


def _snapshot(
    *,
    minutes: int,
    evidence_hash: str | None = HASH_A,
    contract: str | None = CONTRACT_V1,
    execution_id: str | None = EXEC_A,
    source_name: str = "personio:bridgingit",
    external_job_id: str | None = "job-42",
    source_url: str | None = "https://bridgingit.jobs.personio.de/job/42",
) -> RecurringObservationSnapshot:
    return RecurringObservationSnapshot(
        source_name=source_name,
        external_job_id=external_job_id,
        source_url=source_url,
        observed_at=BASE + timedelta(minutes=minutes),
        normalized_evidence_hash=evidence_hash,
        evidence_contract_version=contract,
        execution_id=execution_id,
    )


def test_first_valid_execution_is_baseline_not_unchanged() -> None:
    events = project_recurring_observation_deltas([_snapshot(minutes=0)])

    assert len(events) == 1
    assert events[0].classification == RecurringObservationClassification.BASELINE_ONLY
    assert events[0].delta_kind == RecurringDeltaKind.NEW
    assert events[0].comparable_pair is False
    assert events[0].current_execution_id == EXEC_A
    assert events[0].provider_model_eligible is False
    assert events[0].product_authority is False

    summary = recurring_observation_delta_summary(events)
    assert summary["comparable_pairs"] == 0
    assert summary["unchanged_changed_distribution_available"] is False
    assert summary["unchanged_fraction"] is None
    assert summary["changed_fraction"] is None


def test_same_execution_duplicate_does_not_create_recurring_pair() -> None:
    events = project_recurring_observation_deltas(
        [_snapshot(minutes=0), _snapshot(minutes=1)]
    )

    assert len(events) == 1
    assert events[0].classification == RecurringObservationClassification.BASELINE_ONLY
    assert events[0].execution_observation_count == 2
    assert events[0].same_execution_duplicate_observations == 1

    summary = recurring_observation_delta_summary(events)
    assert summary["same_execution_duplicate_observations"] == 1
    assert summary["comparable_pairs"] == 0
    assert summary["unchanged_changed_distribution_available"] is False


def test_same_execution_conflicting_evidence_fails_closed_and_cannot_be_baseline() -> None:
    events = project_recurring_observation_deltas(
        [
            _snapshot(minutes=0),
            _snapshot(minutes=1, evidence_hash=HASH_B),
            _snapshot(minutes=2, execution_id=EXEC_B),
        ]
    )

    assert events[0].classification == RecurringObservationClassification.SAME_EXECUTION_CONFLICT
    assert events[0].comparable_pair is False
    assert events[0].execution_observation_count == 2
    assert events[1].classification == RecurringObservationClassification.BASELINE_ONLY
    assert recurring_observation_delta_summary(events)["comparable_pairs"] == 0


def test_distinct_execution_same_contract_same_hash_is_truthfully_unchanged() -> None:
    events = project_recurring_observation_deltas(
        [
            _snapshot(minutes=0, execution_id=EXEC_A),
            _snapshot(minutes=1, execution_id=EXEC_B),
        ]
    )

    pair = events[-1]
    assert pair.classification == RecurringObservationClassification.UNCHANGED
    assert pair.delta_kind == RecurringDeltaKind.UNCHANGED
    assert pair.previous_execution_id == EXEC_A
    assert pair.current_execution_id == EXEC_B
    assert pair.comparable_pair is True

    summary = recurring_observation_delta_summary(events)
    assert summary["comparable_pairs"] == 1
    assert summary["unchanged_pairs"] == 1
    assert summary["changed_pairs"] == 0
    assert summary["unchanged_fraction"] == 1.0
    assert summary["changed_fraction"] == 0.0
    assert summary["provider_requests"] == 0
    assert summary["llm_requests"] == 0
    assert summary["product_authority"] is False


def test_distinct_execution_same_contract_different_hash_is_truthfully_changed() -> None:
    events = project_recurring_observation_deltas(
        [
            _snapshot(minutes=0, execution_id=EXEC_A),
            _snapshot(minutes=1, execution_id=EXEC_B, evidence_hash=HASH_B),
        ]
    )

    pair = events[-1]
    assert pair.classification == RecurringObservationClassification.EVIDENCE_CHANGED
    assert pair.delta_kind == RecurringDeltaKind.EVIDENCE_CHANGED
    assert pair.comparable_pair is True

    summary = recurring_observation_delta_summary(events)
    assert summary["unchanged_pairs"] == 0
    assert summary["changed_pairs"] == 1
    assert summary["changed_fraction"] == 1.0


def test_contract_change_between_executions_is_boundary_not_content_change() -> None:
    events = project_recurring_observation_deltas(
        [
            _snapshot(minutes=0, execution_id=EXEC_A),
            _snapshot(minutes=1, execution_id=EXEC_B, contract=CONTRACT_V2),
            _snapshot(minutes=2, execution_id=EXEC_C, contract=CONTRACT_V2),
        ]
    )

    assert events[1].classification == RecurringObservationClassification.CONTRACT_BOUNDARY
    assert events[1].delta_kind == RecurringDeltaKind.CONTRACT_CHANGED
    assert events[1].comparable_pair is False
    assert events[2].classification == RecurringObservationClassification.UNCHANGED
    assert events[2].comparable_pair is True


def test_historical_missing_execution_is_incomparable_and_never_inferred() -> None:
    events = project_recurring_observation_deltas(
        [
            _snapshot(minutes=0, execution_id=None),
            _snapshot(minutes=1, execution_id=EXEC_A),
            _snapshot(minutes=2, execution_id=EXEC_B),
        ]
    )

    assert events[0].classification == (
        RecurringObservationClassification.INCOMPARABLE_MISSING_EXECUTION
    )
    assert events[0].delta_kind is None
    assert events[1].classification == RecurringObservationClassification.BASELINE_ONLY
    assert events[2].classification == RecurringObservationClassification.UNCHANGED


def test_missing_evidence_inside_correlated_history_breaks_comparison_chain() -> None:
    events = project_recurring_observation_deltas(
        [
            _snapshot(minutes=0, execution_id=EXEC_A),
            _snapshot(
                minutes=1,
                execution_id=EXEC_B,
                evidence_hash=None,
                contract=None,
            ),
            _snapshot(minutes=2, execution_id=EXEC_C),
        ]
    )

    assert events[0].classification == RecurringObservationClassification.BASELINE_ONLY
    assert events[1].classification == (
        RecurringObservationClassification.INCOMPARABLE_MISSING_EVIDENCE
    )
    assert events[2].classification == RecurringObservationClassification.BASELINE_ONLY
    assert recurring_observation_delta_summary(events)["comparable_pairs"] == 0


def test_pair_classifier_rejects_same_execution_as_recurrence() -> None:
    duplicate = classify_observation_pair(
        previous=_snapshot(minutes=0, execution_id=EXEC_A),
        current=_snapshot(minutes=1, execution_id=EXEC_A),
    )
    conflict = classify_observation_pair(
        previous=_snapshot(minutes=0, execution_id=EXEC_A),
        current=_snapshot(minutes=1, execution_id=EXEC_A, evidence_hash=HASH_B),
    )

    assert duplicate.classification == RecurringObservationClassification.SAME_EXECUTION_DUPLICATE
    assert duplicate.comparable_pair is False
    assert conflict.classification == RecurringObservationClassification.SAME_EXECUTION_CONFLICT
    assert conflict.comparable_pair is False


def test_invalid_hash_contract_and_execution_values_fail_closed() -> None:
    with pytest.raises(ValueError, match="both null or both present"):
        _snapshot(minutes=0, evidence_hash=HASH_A, contract=None)
    with pytest.raises(ValueError, match="SHA-256"):
        _snapshot(minutes=0, evidence_hash="not-a-hash", contract=CONTRACT_V1)
    with pytest.raises(ValueError, match="non-empty"):
        _snapshot(minutes=0, evidence_hash=HASH_A, contract=" ")
    with pytest.raises(ValueError, match="UUID"):
        _snapshot(minutes=0, execution_id="not-an-execution-id")


def test_missing_source_local_identity_fails_closed() -> None:
    with pytest.raises(ValueError, match="external_job_id or source_url"):
        _snapshot(minutes=0, external_job_id=" ", source_url=None)


def test_pair_identity_mismatch_and_lookalike_source_name_remain_untrusted() -> None:
    previous = _snapshot(minutes=0, source_name="personio:bridgingit", execution_id=EXEC_A)
    lookalike = _snapshot(minutes=1, source_name="personio:bridging-it", execution_id=EXEC_B)

    evidence = classify_observation_pair(previous=previous, current=lookalike)

    assert evidence.classification == RecurringObservationClassification.IDENTITY_MISMATCH
    assert evidence.delta_kind == RecurringDeltaKind.CACHE_IDENTITY_MISMATCH
    assert evidence.comparable_pair is False
    assert evidence.provider_model_eligible is False


def test_external_id_is_identity_authority_and_url_is_only_fallback() -> None:
    previous = _snapshot(
        minutes=0,
        external_job_id="job-42",
        source_url="https://example.test/old-route",
    )
    current = _snapshot(
        minutes=1,
        external_job_id="job-42",
        source_url="https://example.test/new-route",
    )
    assert previous.identity_key == current.identity_key

    previous_without_id = _snapshot(
        minutes=0,
        external_job_id=None,
        source_url="https://example.test/old-route",
    )
    current_without_id = _snapshot(
        minutes=1,
        external_job_id=None,
        source_url="https://example.test/new-route",
    )
    assert previous_without_id.identity_key != current_without_id.identity_key


def test_non_forward_timestamp_breaks_chain_and_next_valid_execution_rebaselines() -> None:
    events = project_recurring_observation_deltas(
        [
            _snapshot(minutes=2, execution_id=EXEC_A),
            _snapshot(minutes=1, execution_id=EXEC_B),
            _snapshot(minutes=3, execution_id=EXEC_C),
        ]
    )

    assert events[0].classification == RecurringObservationClassification.BASELINE_ONLY
    assert events[1].classification == RecurringObservationClassification.NON_FORWARD_TIMESTAMP
    assert events[1].comparable_pair is False
    assert events[2].classification == RecurringObservationClassification.BASELINE_ONLY


def test_execution_reentry_after_completion_fails_closed() -> None:
    events = project_recurring_observation_deltas(
        [
            _snapshot(minutes=0, execution_id=EXEC_A),
            _snapshot(minutes=1, execution_id=EXEC_B),
            _snapshot(minutes=2, execution_id=EXEC_A),
        ]
    )

    assert events[0].classification == RecurringObservationClassification.BASELINE_ONLY
    assert events[1].classification == RecurringObservationClassification.UNCHANGED
    assert events[2].classification == RecurringObservationClassification.EXECUTION_REENTRY
    assert events[2].comparable_pair is False


def test_interleaved_identities_compare_only_across_their_own_distinct_executions() -> None:
    observations = [
        _snapshot(minutes=0, external_job_id="job-a", execution_id=EXEC_A),
        _snapshot(minutes=0, external_job_id="job-b", execution_id=EXEC_A),
        _snapshot(minutes=1, external_job_id="job-a", execution_id=EXEC_B),
        _snapshot(
            minutes=1,
            external_job_id="job-b",
            execution_id=EXEC_B,
            evidence_hash=HASH_B,
        ),
    ]

    events = project_recurring_observation_deltas(observations)
    summary = recurring_observation_delta_summary(events)

    assert [event.classification for event in events] == [
        RecurringObservationClassification.BASELINE_ONLY,
        RecurringObservationClassification.BASELINE_ONLY,
        RecurringObservationClassification.UNCHANGED,
        RecurringObservationClassification.EVIDENCE_CHANGED,
    ]
    assert summary["identity_count"] == 2
    assert summary["comparable_pairs"] == 2
    assert summary["unchanged_pairs"] == 1
    assert summary["changed_pairs"] == 1
    assert summary["unchanged_fraction"] == 0.5
    assert summary["changed_fraction"] == 0.5


def test_mapping_projection_accepts_postgres_uuid_and_remains_product_neutral() -> None:
    snapshot = RecurringObservationSnapshot.from_mapping(
        {
            "source_name": "personio:bridgingit",
            "external_job_id": "job-42",
            "source_url": "https://bridgingit.jobs.personio.de/job/42",
            "observed_at": BASE,
            "normalized_evidence_hash": HASH_A,
            "evidence_contract_version": CONTRACT_V1,
            "execution_id": UUID(EXEC_A),
        }
    )
    event = project_recurring_observation_deltas([snapshot])[0]
    payload = event.to_json()

    assert payload["projection_version"] == RECURRING_OBSERVATION_DELTA_PROJECTION_VERSION
    assert payload["classification"] == "baseline_only"
    assert payload["delta_kind"] == "new"
    assert payload["current_execution_id"] == EXEC_A
    assert payload["provider_model_eligible"] is False
    assert payload["product_authority"] is False
