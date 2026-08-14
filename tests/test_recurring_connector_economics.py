from __future__ import annotations

import pytest

from src.search_intelligence.llm_booster_policy import (
    BoosterStage,
    TavilyState,
    eligible_stage_names,
)
from src.search_intelligence.recurring_connector_economics import (
    OpportunityCostObservation,
    RecurringDeltaKind,
    RecurringDeterministicOutcome,
    RecurringGapKind,
    RecurringOpportunityCostLedger,
    build_recurring_connector_decision,
    build_recurring_evidence_record,
    classify_recurring_delta,
    normalized_evidence_hash,
    source_local_job_identity,
)


def _record(
    *,
    evidence: dict[str, object],
    outcome: RecurringDeterministicOutcome = RecurringDeterministicOutcome.UNRESOLVED,
    connector_id: str = "personio:acme",
    external_job_id: str | None = "job-123",
    source_url: str | None = "https://jobs.example.test/123",
    contract_version: str = "LLM-BOOST-001.v1",
):
    return build_recurring_evidence_record(
        connector_id=connector_id,
        external_job_id=external_job_id,
        source_url=source_url,
        evidence=evidence,
        deterministic_outcome=outcome,
        contract_version=contract_version,
    )


def test_normalized_evidence_hash_is_stable_for_key_order_and_whitespace() -> None:
    first = normalized_evidence_hash(
        {
            "title": "  Senior   Data Engineer ",
            "location": {"city": "Hannover", "remote": True},
        }
    )
    same = normalized_evidence_hash(
        {
            "location": {"remote": True, "city": "Hannover"},
            "title": "Senior Data Engineer",
        }
    )
    assert first == same
    assert len(first) == 64


def test_normalized_evidence_hash_preserves_sequence_order() -> None:
    first = normalized_evidence_hash({"skills": ["Python", "SQL"]})
    changed = normalized_evidence_hash({"skills": ["SQL", "Python"]})
    assert first != changed


def test_normalized_evidence_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        normalized_evidence_hash({"score": float("nan")})


def test_source_local_identity_prefers_external_id_and_falls_back_to_url() -> None:
    assert source_local_job_identity(
        external_job_id=" 42 ",
        source_url="https://example.test/jobs/42",
    ) == "external_id:42"
    assert source_local_job_identity(
        external_job_id=None,
        source_url=" https://example.test/jobs/42 ",
    ) == "source_url:https://example.test/jobs/42"
    with pytest.raises(ValueError, match="external_job_id or source_url"):
        source_local_job_identity(external_job_id=" ", source_url=None)


def test_same_evidence_and_contract_is_unchanged() -> None:
    previous = _record(evidence={"title": "Data Engineer"})
    current = _record(evidence={"title": "Data   Engineer"})
    assert current.fingerprint == previous.fingerprint
    assert classify_recurring_delta(current=current, previous=previous) == RecurringDeltaKind.UNCHANGED


def test_changed_evidence_invalidates_cache() -> None:
    previous = _record(evidence={"title": "Data Engineer"})
    current = _record(evidence={"title": "Senior Data Engineer"})
    assert classify_recurring_delta(current=current, previous=previous) == RecurringDeltaKind.EVIDENCE_CHANGED


def test_contract_change_invalidates_cache_even_when_evidence_is_same() -> None:
    previous = _record(
        evidence={"title": "Data Engineer"},
        contract_version="LLM-BOOST-001.v1",
    )
    current = _record(
        evidence={"title": "Data Engineer"},
        contract_version="LLM-BOOST-001.v2",
    )
    assert classify_recurring_delta(current=current, previous=previous) == RecurringDeltaKind.CONTRACT_CHANGED


def test_cache_identity_mismatch_fails_closed() -> None:
    previous = _record(evidence={"title": "Data Engineer"})
    current = _record(
        evidence={"title": "Data Engineer"},
        external_job_id="job-999",
    )
    decision = build_recurring_connector_decision(
        current=current,
        previous=previous,
        gap_kind=RecurringGapKind.EXTERNAL_INFORMATION,
        tavily_state=TavilyState.AVAILABLE,
    )
    assert decision.delta_kind == RecurringDeltaKind.CACHE_IDENTITY_MISMATCH
    assert decision.booster_eligible is False
    assert decision.booster_plan is None
    assert decision.reason_code == "recurring_cache_identity_mismatch"


@pytest.mark.parametrize(
    "outcome",
    [
        RecurringDeterministicOutcome.SUPPORTED,
        RecurringDeterministicOutcome.UNRESOLVED,
    ],
)
def test_unchanged_evidence_suppresses_every_external_stage(outcome) -> None:
    previous = _record(evidence={"title": "Data Engineer"}, outcome=outcome)
    current = _record(evidence={"title": "Data Engineer"}, outcome=outcome)
    decision = build_recurring_connector_decision(
        current=current,
        previous=previous,
        gap_kind=RecurringGapKind.EXTERNAL_INFORMATION,
        tavily_state=TavilyState.AVAILABLE,
    )
    assert decision.booster_eligible is False
    assert decision.reason_code == "unchanged_recurring_evidence_fingerprint"
    assert decision.booster_plan is not None
    assert eligible_stage_names(decision.booster_plan) == (BoosterStage.DETERMINISTIC.value,)
    payload = decision.to_json()
    assert payload["provider_requests"] == 0
    assert payload["llm_requests"] == 0
    assert payload["database_requests"] == 0
    assert payload["product_writes"] == 0
    assert payload["product_authority"] is False


def test_new_evidence_requires_deterministic_parse_before_booster() -> None:
    current = _record(
        evidence={"title": "Data Engineer"},
        outcome=RecurringDeterministicOutcome.NOT_RUN,
    )
    decision = build_recurring_connector_decision(
        current=current,
        previous=None,
        gap_kind=RecurringGapKind.SEMANTIC_AMBIGUITY,
        tavily_state=TavilyState.AVAILABLE,
    )
    assert decision.delta_kind == RecurringDeltaKind.NEW
    assert decision.booster_eligible is False
    assert decision.booster_plan is None
    assert decision.reason_code == "deterministic_parse_required_before_booster"


def test_deterministically_supported_changed_evidence_skips_boosters() -> None:
    previous = _record(evidence={"title": "Data Engineer"})
    current = _record(
        evidence={"title": "Senior Data Engineer"},
        outcome=RecurringDeterministicOutcome.SUPPORTED,
    )
    decision = build_recurring_connector_decision(
        current=current,
        previous=previous,
        gap_kind=RecurringGapKind.SEMANTIC_AMBIGUITY,
        tavily_state=TavilyState.AVAILABLE,
    )
    assert decision.delta_kind == RecurringDeltaKind.EVIDENCE_CHANGED
    assert decision.booster_eligible is False
    assert decision.booster_plan is not None
    assert eligible_stage_names(decision.booster_plan) == (BoosterStage.DETERMINISTIC.value,)


def test_changed_semantic_ambiguity_skips_tavily_and_allows_models() -> None:
    previous = _record(evidence={"description": "Data platform"})
    current = _record(evidence={"description": "Senior data platform role"})
    decision = build_recurring_connector_decision(
        current=current,
        previous=previous,
        gap_kind=RecurringGapKind.SEMANTIC_AMBIGUITY,
        tavily_state=TavilyState.AVAILABLE,
    )
    assert decision.booster_eligible is True
    assert decision.booster_plan is not None
    eligible = eligible_stage_names(decision.booster_plan)
    assert BoosterStage.TAVILY.value not in eligible
    assert BoosterStage.LUNA_MEDIUM.value in eligible
    assert BoosterStage.TERRA_MEDIUM.value in eligible
    assert decision.product_authority is False


def test_changed_external_information_gap_allows_search_before_models() -> None:
    previous = _record(evidence={"detail_url": "https://example.test/old"})
    current = _record(evidence={"detail_url": "https://example.test/new"})
    decision = build_recurring_connector_decision(
        current=current,
        previous=previous,
        gap_kind=RecurringGapKind.EXTERNAL_INFORMATION,
        tavily_state=TavilyState.AVAILABLE,
    )
    assert decision.booster_eligible is True
    assert decision.booster_plan is not None
    eligible = eligible_stage_names(decision.booster_plan)
    assert eligible[:3] == (
        BoosterStage.DETERMINISTIC.value,
        BoosterStage.TAVILY.value,
        BoosterStage.LUNA_MEDIUM.value,
    )


def test_unclassified_unresolved_delta_does_not_auto_escalate() -> None:
    current = _record(evidence={"title": "Data Engineer"})
    decision = build_recurring_connector_decision(
        current=current,
        previous=None,
        gap_kind=RecurringGapKind.NONE,
        tavily_state=TavilyState.AVAILABLE,
    )
    assert decision.booster_eligible is False
    assert decision.booster_plan is None
    assert decision.reason_code == "unclassified_recurring_unresolved"


def test_opportunity_cost_ledger_suppresses_duplicate_stage_observations() -> None:
    record = _record(evidence={"title": "Senior Data Engineer"})
    observation = OpportunityCostObservation(
        fingerprint=record.fingerprint,
        delta_kind=RecurringDeltaKind.EVIDENCE_CHANGED,
        gap_kind=RecurringGapKind.SEMANTIC_AMBIGUITY,
        stage=BoosterStage.LUNA_MEDIUM,
        provider_requests=1,
        llm_requests=1,
        cost_usd=0.004,
        latency_ms=1250,
        validated_rescue=True,
        progressed=True,
    )
    ledger = RecurringOpportunityCostLedger()
    assert ledger.record(observation) is True
    assert ledger.record(observation) is False
    assert ledger.contains(
        fingerprint=record.fingerprint,
        stage=BoosterStage.LUNA_MEDIUM,
    )
    assert ledger.summary() == {
        "observation_count": 1,
        "unique_fingerprints": 1,
        "provider_requests": 1,
        "llm_requests": 1,
        "total_cost_usd": 0.004,
        "total_latency_ms": 1250,
        "validated_rescues": 1,
        "cost_per_validated_rescue_usd": 0.004,
        "stage_observations": {"luna_medium": 1},
        "duplicate_observations_suppressed": 1,
        "product_authority": False,
    }


def test_opportunity_cost_ledger_rejects_spend_on_unchanged_evidence() -> None:
    record = _record(evidence={"title": "Data Engineer"})
    with pytest.raises(ValueError, match="unchanged recurring evidence"):
        OpportunityCostObservation(
            fingerprint=record.fingerprint,
            delta_kind=RecurringDeltaKind.UNCHANGED,
            gap_kind=RecurringGapKind.SEMANTIC_AMBIGUITY,
            stage=BoosterStage.LUNA_MEDIUM,
            provider_requests=1,
            llm_requests=1,
            cost_usd=0.004,
        )
