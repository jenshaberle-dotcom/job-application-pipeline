from __future__ import annotations

import pytest

from src.search_intelligence.booster_admission import (
    BoosterAdmissionPolicy,
    BoosterFamily,
    BoosterOpportunityEvidence,
    evaluate_booster_admission,
    rank_shadow_candidates,
)


POLICY = BoosterAdmissionPolicy(
    minimum_expected_net_value=5.0,
    minimum_problem_fit=0.6,
    minimum_evidence_quality=0.6,
    maximum_operational_risk=0.4,
    minimum_ml_repeatability=0.7,
    minimum_ml_decision_volume=100,
)


def _opportunity(
    *,
    surface_id: str = "job_review_relevance",
    family: BoosterFamily = BoosterFamily.ML,
    decision_volume: int = 500,
    residual_rate: float = 0.4,
    rescue_rate: float = 0.2,
    value_per_rescue: float = 2.0,
    cost_per_case: float = 0.01,
    fixed_cost: float = 5.0,
    problem_fit: float = 0.9,
    evidence_quality: float = 0.9,
    repeatability: float = 0.95,
    operational_risk: float = 0.2,
    baseline_measured: bool = True,
    grounded_evaluation_ready: bool = True,
    observability_ready: bool = True,
    authority_boundary_defined: bool = True,
) -> BoosterOpportunityEvidence:
    return BoosterOpportunityEvidence(
        surface_id=surface_id,
        family=family,
        baseline_measured=baseline_measured,
        decision_volume=decision_volume,
        deterministic_residual_rate=residual_rate,
        expected_rescue_rate=rescue_rate,
        expected_value_per_rescue=value_per_rescue,
        estimated_incremental_cost_per_escalated_case=cost_per_case,
        estimated_fixed_validation_cost=fixed_cost,
        problem_fit=problem_fit,
        evidence_quality=evidence_quality,
        repeatability=repeatability,
        operational_risk=operational_risk,
        grounded_evaluation_ready=grounded_evaluation_ready,
        observability_ready=observability_ready,
        authority_boundary_defined=authority_boundary_defined,
    )


def test_high_value_repeatable_ml_surface_is_shadow_candidate_only() -> None:
    decision = evaluate_booster_admission(_opportunity(), POLICY)

    assert decision.eligible_for_shadow is True
    assert decision.reasons == ()
    assert decision.expected_escalated_cases == pytest.approx(200.0)
    assert decision.expected_rescues == pytest.approx(40.0)
    assert decision.expected_gross_value == pytest.approx(80.0)
    assert decision.expected_variable_cost == pytest.approx(2.0)
    assert decision.expected_fixed_cost == pytest.approx(5.0)
    assert decision.expected_net_value == pytest.approx(73.0)
    assert decision.execution_authorized is False
    assert decision.product_authority is False


def test_expected_value_is_calculated_only_on_the_measured_residual() -> None:
    decision = evaluate_booster_admission(
        _opportunity(
            decision_volume=1_000,
            residual_rate=0.1,
            rescue_rate=0.5,
            value_per_rescue=1.0,
            cost_per_case=0.1,
            fixed_cost=0.0,
        ),
        POLICY,
    )

    assert decision.expected_escalated_cases == pytest.approx(100.0)
    assert decision.expected_rescues == pytest.approx(50.0)
    assert decision.expected_gross_value == pytest.approx(50.0)
    assert decision.expected_variable_cost == pytest.approx(10.0)
    assert decision.expected_net_value == pytest.approx(40.0)


def test_ml_is_rejected_when_surface_is_not_repeatable_even_if_value_is_high() -> None:
    decision = evaluate_booster_admission(
        _opportunity(repeatability=0.2, value_per_rescue=10.0),
        POLICY,
    )

    assert decision.eligible_for_shadow is False
    assert "ml_repeatability_below_threshold" in decision.reasons


def test_llm_surface_does_not_inherit_ml_volume_or_repeatability_gate() -> None:
    decision = evaluate_booster_admission(
        _opportunity(
            surface_id="unusual_ats_semantics",
            family=BoosterFamily.LLM,
            decision_volume=20,
            residual_rate=0.5,
            rescue_rate=0.8,
            value_per_rescue=3.0,
            fixed_cost=0.0,
            repeatability=0.1,
        ),
        POLICY,
    )

    assert decision.eligible_for_shadow is True
    assert "ml_repeatability_below_threshold" not in decision.reasons
    assert "ml_volume_below_threshold" not in decision.reasons


def test_missing_baseline_grounding_observability_or_authority_blocks_shadow() -> None:
    decision = evaluate_booster_admission(
        _opportunity(
            baseline_measured=False,
            grounded_evaluation_ready=False,
            observability_ready=False,
            authority_boundary_defined=False,
        ),
        POLICY,
    )

    assert decision.eligible_for_shadow is False
    assert decision.reasons[:4] == (
        "baseline_not_measured",
        "grounded_evaluation_missing",
        "observability_missing",
        "authority_boundary_missing",
    )


def test_zero_residual_does_not_create_a_booster_surface() -> None:
    decision = evaluate_booster_admission(
        _opportunity(residual_rate=0.0, fixed_cost=0.0),
        POLICY,
    )

    assert decision.eligible_for_shadow is False
    assert "no_measured_residual" in decision.reasons


def test_shadow_candidates_are_ranked_by_expected_net_value_not_pipeline_order() -> None:
    candidates = rank_shadow_candidates(
        (
            _opportunity(
                surface_id="low_value_surface",
                value_per_rescue=0.5,
                fixed_cost=0.0,
            ),
            _opportunity(
                surface_id="job_review_relevance",
                value_per_rescue=3.0,
                fixed_cost=0.0,
            ),
            _opportunity(
                surface_id="blocked_surface",
                value_per_rescue=100.0,
                grounded_evaluation_ready=False,
            ),
        ),
        POLICY,
    )

    assert [candidate.surface_id for candidate in candidates] == [
        "job_review_relevance",
        "low_value_surface",
    ]
    assert all(candidate.execution_authorized is False for candidate in candidates)


def test_invalid_probability_inputs_fail_closed() -> None:
    with pytest.raises(ValueError, match="repeatability must be between 0 and 1"):
        _opportunity(repeatability=1.1)

    with pytest.raises(ValueError, match="minimum_problem_fit must be between 0 and 1"):
        BoosterAdmissionPolicy(
            minimum_expected_net_value=0.0,
            minimum_problem_fit=-0.1,
            minimum_evidence_quality=0.5,
            maximum_operational_risk=0.5,
            minimum_ml_repeatability=0.5,
            minimum_ml_decision_volume=0,
        )
