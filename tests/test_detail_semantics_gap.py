from __future__ import annotations

import pytest

from src.search_intelligence.detail_semantics_gap import analyze_detail_semantics_gap
from src.search_intelligence.llm_booster_policy import BoosterStage, TavilyState


DETAIL_URL = "https://jobs.example.com/jobs/42-data-engineer"


def decide(
    *,
    deterministic_attempted: bool = True,
    detail_supported: bool = True,
    profile_contract_satisfied: bool = False,
    geography_contract_satisfied: bool = False,
    fields: dict[str, object] | None = None,
    references: tuple[dict[str, object], ...] = (),
    tavily_state: TavilyState = TavilyState.AVAILABLE,
    previous_semantic_fingerprint: str | None = None,
):
    return analyze_detail_semantics_gap(
        candidate_id=42,
        company_key="example",
        detail_url=DETAIL_URL,
        deterministic_attempted=deterministic_attempted,
        detail_supported=detail_supported,
        profile_contract_satisfied=profile_contract_satisfied,
        geography_contract_satisfied=geography_contract_satisfied,
        deterministic_semantic_fields=fields or {},
        evidence_references=references,
        tavily_state=tavily_state,
        previous_semantic_fingerprint=previous_semantic_fingerprint,
    )


def stage(decision, target: BoosterStage):  # type: ignore[no-untyped-def]
    return next(item for item in decision.booster_plan.stages if item.stage == target)


def test_deterministic_profile_and_geography_success_resolves_semantics() -> None:
    decision = decide(
        profile_contract_satisfied=True,
        geography_contract_satisfied=True,
        fields={
            "role": "Data Engineer",
            "location": "Hannover",
            "remote": "hybrid",
        },
    )

    assert decision.classification == "detail_semantics_resolved"
    assert decision.deterministic_resolved is True
    assert decision.missing_contracts == ()
    assert decision.semantic_booster_eligible is False
    assert decision.semantic_authority is False
    assert decision.product_authority is False
    assert all(not item.eligible for item in decision.booster_plan.stages[1:])


def test_unexecuted_deterministic_semantics_blocks_external_stages() -> None:
    decision = decide(deterministic_attempted=False)

    assert decision.classification == "detail_semantics_d0_required"
    assert decision.semantic_booster_eligible is False
    assert decision.next_action == "run_deterministic_detail_semantics"
    assert all(not item.eligible for item in decision.booster_plan.stages[1:])


def test_unsupported_detail_truth_blocks_semantic_booster() -> None:
    decision = decide(detail_supported=False)

    assert decision.classification == "detail_semantics_requires_supported_detail"
    assert decision.semantic_booster_eligible is False
    assert decision.next_action == "preserve_detail_truth_and_stop_semantic_booster"
    assert all(not item.eligible for item in decision.booster_plan.stages[1:])


def test_semantic_ambiguity_skips_tavily_and_allows_model_hypotheses() -> None:
    decision = decide(
        profile_contract_satisfied=True,
        geography_contract_satisfied=False,
        fields={"role": "Data Engineer", "skills": ["Python", "SQL"]},
    )

    assert decision.classification == "detail_semantics_ambiguity_gap"
    assert decision.missing_contracts == ("geography",)
    assert decision.external_information_gap is False
    assert decision.semantic_booster_eligible is True
    assert stage(decision, BoosterStage.TAVILY).eligible is False
    assert stage(decision, BoosterStage.TAVILY).reason_code == "external_search_not_indicated"
    assert stage(decision, BoosterStage.LUNA_MEDIUM).eligible is True
    assert stage(decision, BoosterStage.TERRA_MEDIUM).eligible is True
    assert stage(decision, BoosterStage.SOL_MEDIUM).eligible is True
    assert stage(decision, BoosterStage.LUNA_MAX).eligible is True


def test_tavily_state_never_turns_ordinary_semantic_ambiguity_into_search() -> None:
    for state in TavilyState:
        decision = decide(tavily_state=state)
        assert stage(decision, BoosterStage.TAVILY).eligible is False
        assert stage(decision, BoosterStage.LUNA_MEDIUM).eligible is True


def test_unchanged_semantic_fingerprint_suppresses_model_spend() -> None:
    first = decide(fields={"role": "Data Engineer"})
    second = decide(
        fields={"role": "Data Engineer"},
        previous_semantic_fingerprint=first.evidence_fingerprint,
    )

    assert second.classification == "detail_semantics_gap_unchanged"
    assert second.unchanged_evidence_skip is True
    assert second.semantic_booster_eligible is False
    assert second.next_action == "await_changed_detail_semantic_evidence"
    assert all(not item.eligible for item in second.booster_plan.stages[1:])


def test_evidence_reference_change_invalidates_semantic_fingerprint() -> None:
    first = decide(
        references=(
            {
                "field": "location",
                "source_url": DETAIL_URL,
                "evidence": "Arbeitsort: Hannover",
                "value": "Hannover",
                "span_start": 10,
                "span_end": 30,
            },
        )
    )
    second = decide(
        references=(
            {
                "field": "location",
                "source_url": DETAIL_URL,
                "evidence": "Arbeitsort: Deutschlandweit",
                "value": "Deutschlandweit",
                "span_start": 10,
                "span_end": 37,
            },
        )
    )

    assert first.evidence_fingerprint != second.evidence_fingerprint
    reference = first.evidence_references[0]
    assert reference.field == "location"
    assert reference.source_url == DETAIL_URL
    assert reference.span_start == 10
    assert reference.span_end == 30


def test_unknown_semantic_reference_field_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported Detail Semantics evidence field"):
        decide(
            references=(
                {
                    "field": "salary",
                    "source_url": DETAIL_URL,
                    "evidence": "100k",
                },
            )
        )


def test_decision_never_grants_semantic_or_product_authority() -> None:
    decision = decide()

    assert decision.semantic_authority is False
    assert decision.product_authority is False
    assert decision.booster_plan.product_authority is False
    assert decision.booster_plan.product_writes == 0
    assert decision.booster_plan.provider_network_requests == 0
    assert decision.booster_plan.llm_requests == 0
    assert decision.booster_plan.database_requests == 0
