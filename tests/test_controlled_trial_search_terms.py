from datetime import datetime, timezone
from decimal import Decimal

from src.search_intelligence.trial_application import (
    TRIAL_APPROVAL_TOKEN,
    StrategyRecommendationForTrial,
    build_trial_application_plans,
)


def recommendation(status: str = "pending_review") -> StrategyRecommendationForTrial:
    return StrategyRecommendationForTrial(
        recommendation_id=1,
        candidate_id=2,
        company_key="hdi",
        source_name_candidate="hdi:hannover",
        source_family_candidate="hdi",
        suggested_term="analytics",
        recommendation_type="ADD_TRIAL_TERM",
        recommendation_status=status,
        autonomy_level="manual_approval_required",
        guardrail_decision="bounded_trial_recommended",
        confidence_score=Decimal("100.00"),
        sample_size=1,
        false_negative_risk_level="high",
        guardrail_summary={
            "trial_duration_days": 14,
            "max_result_volume": 25,
            "max_noise_rate": "0.30",
        },
        reason="test",
    )


def test_pending_recommendation_requires_trial_approval_token() -> None:
    plans = build_trial_application_plans([recommendation()], now=datetime(2026, 5, 31, tzinfo=timezone.utc))
    assert len(plans) == 1
    assert plans[0].apply_allowed is False
    assert plans[0].approval_required is True


def test_approval_token_allows_bounded_trial_application() -> None:
    plans = build_trial_application_plans(
        [recommendation()],
        approval_token=TRIAL_APPROVAL_TOKEN,
        now=datetime(2026, 5, 31, tzinfo=timezone.utc),
    )
    assert plans[0].apply_allowed is True
    assert plans[0].trial_duration_days == 14
    assert plans[0].max_result_volume == 25


def test_auto_eligible_requires_explicit_auto_mode() -> None:
    item = recommendation(status="auto_eligible")
    assert build_trial_application_plans([item])[0].apply_allowed is False
    assert build_trial_application_plans([item], allow_auto_eligible=True)[0].apply_allowed is True
