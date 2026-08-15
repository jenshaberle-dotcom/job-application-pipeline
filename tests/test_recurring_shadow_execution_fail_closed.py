from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.search_intelligence.llm_booster_policy import TavilyState
from src.search_intelligence.recurring_connector_economics import (
    RecurringDeterministicOutcome,
    RecurringGapKind,
    RecurringOpportunityCostLedger,
    build_recurring_evidence_record,
)
from src.search_intelligence.recurring_observation_delta_projection import (
    RecurringObservationSnapshot,
    project_recurring_observation_deltas,
)
from src.search_intelligence.recurring_shadow_execution import (
    RecurringShadowHypothesisObservation,
    execute_recurring_shadow,
)
from src.search_intelligence.recurring_shadow_selection import (
    select_recurring_shadow_candidate,
)


def test_eligible_stage_that_reports_no_request_fails_closed_before_validation() -> None:
    current = build_recurring_evidence_record(
        connector_id="personio:bridgingit",
        external_job_id="job-42",
        source_url="https://bridgingit.jobs.personio.de/job/42",
        evidence={"title": "Current", "location": "Hannover"},
        deterministic_outcome=RecurringDeterministicOutcome.UNRESOLVED,
    )
    previous_hash = "a" * 64
    if previous_hash == current.normalized_evidence_hash:
        previous_hash = "b" * 64
    base = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
    projection = project_recurring_observation_deltas(
        [
            RecurringObservationSnapshot(
                source_name="personio:bridgingit",
                external_job_id="job-42",
                source_url="https://bridgingit.jobs.personio.de/job/42",
                observed_at=base,
                normalized_evidence_hash=previous_hash,
                evidence_contract_version="recurring-observation-evidence.v1",
                execution_id="11111111-1111-4111-8111-111111111111",
            ),
            RecurringObservationSnapshot(
                source_name="personio:bridgingit",
                external_job_id="job-42",
                source_url="https://bridgingit.jobs.personio.de/job/42",
                observed_at=base + timedelta(minutes=1),
                normalized_evidence_hash=current.normalized_evidence_hash,
                evidence_contract_version="recurring-observation-evidence.v1",
                execution_id="22222222-2222-4222-8222-222222222222",
            ),
        ]
    )[-1]
    selection = select_recurring_shadow_candidate(
        projection=projection,
        current=current,
        gap_kind=RecurringGapKind.SEMANTIC_AMBIGUITY,
        tavily_state=TavilyState.DISABLED,
    )
    assert selection.shadow_sample_eligible is True

    validator_called = False

    def execute_stage(_stage, _context):
        return RecurringShadowHypothesisObservation(
            status="completed",
            request_attempted=False,
            hypothesis={},
            estimated_cost_usd=0.0,
            latency_ms=0,
        )

    def validate(*_args):
        nonlocal validator_called
        validator_called = True
        raise AssertionError("non-attempted eligible stage must not be validated")

    ledger = RecurringOpportunityCostLedger()
    result = execute_recurring_shadow(
        selection=selection,
        current=current,
        shadow_context={},
        ledger=ledger,
        execute_stage=execute_stage,
        validate=validate,
    )

    assert validator_called is False
    luna = next(stage for stage in result.stages if stage.stage.value == "luna_medium")
    assert luna.status == "failed_closed"
    assert luna.reason_code == "eligible_shadow_stage_not_attempted"
    assert result.provider_requests == 0
    assert result.llm_requests == 0
    assert result.estimated_cost_usd == 0.0
    assert result.product_writes == 0
    assert result.product_authority is False
    assert ledger.summary()["observation_count"] == 0
