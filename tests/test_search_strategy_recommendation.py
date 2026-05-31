from decimal import Decimal

from src.search_intelligence.autonomy_policy import AutonomyInput, evaluate_autonomy
from src.search_intelligence.strategy_recommendation import StrategyRecommendationInput, build_strategy_recommendations


def test_single_hdi_success_recommends_manual_bounded_trial() -> None:
    recs = build_strategy_recommendations([
        StrategyRecommendationInput(
            candidate_id=2,
            company_key='hdi',
            source_name_candidate='hdi:hannover',
            source_family_candidate='hdi',
            suggested_term='analytics',
            confidence_score=Decimal('100.00'),
            confidence_level='low',
            sample_size=1,
            success_count=1,
            failure_count=0,
            noise_count=0,
            false_negative_risk_level='high',
            false_negative_sighting_count=2,
        )
    ])

    assert len(recs) == 1
    assert recs[0].recommendation_type == 'ADD_TRIAL_TERM'
    assert recs[0].recommendation_status == 'pending_review'
    assert recs[0].guardrail_decision == 'bounded_trial_recommended'
    assert recs[0].autonomy_level == 'manual_approval_required'


def test_stronger_evidence_becomes_auto_eligible_but_not_auto_applied() -> None:
    decision = evaluate_autonomy(
        AutonomyInput(
            company_key='hdi',
            source_family_candidate='hdi',
            suggested_term='analytics',
            confidence_score=Decimal('80.00'),
            confidence_level='high',
            sample_size=5,
            success_count=4,
            failure_count=1,
            noise_count=0,
            false_negative_risk_level='high',
            false_negative_sighting_count=6,
        )
    )

    assert decision.recommendation_status == 'auto_eligible'
    assert decision.guardrail_decision == 'auto_trial_eligible'
    assert decision.auto_apply_allowed is False
    assert decision.trial_duration_days == 14


def test_noisy_term_is_blocked() -> None:
    decision = evaluate_autonomy(
        AutonomyInput(
            company_key='hdi',
            source_family_candidate='hdi',
            suggested_term='data',
            confidence_score=Decimal('40.00'),
            confidence_level='medium',
            sample_size=5,
            success_count=1,
            failure_count=1,
            noise_count=3,
            false_negative_risk_level='high',
            false_negative_sighting_count=6,
        )
    )

    assert decision.recommendation_type == 'REJECT_TERM'
    assert decision.guardrail_decision == 'blocked_too_noisy'
