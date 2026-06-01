from __future__ import annotations

from decimal import Decimal

from src.search_intelligence.candidate_intelligence import CandidateSkill
from src.search_intelligence.capability_gap import (
    SearchTermSupport,
    build_capability_gap_scores,
    score_capability_gap,
)


def test_capability_gap_prioritizes_high_direction_low_capability_with_market_signal() -> None:
    skill = CandidateSkill("Databricks", "data_engineering", capability_score=20, career_direction_weight=100)
    score = score_capability_gap(
        profile_name="Jens Career Transition",
        profile_version="v1",
        skill=skill,
        supports=[
            SearchTermSupport("databricks", "Databricks", Decimal("85.00"), "high"),
            SearchTermSupport("lakehouse", "Databricks", Decimal("70.00"), "medium"),
        ],
    )

    assert score.skill_name == "Databricks"
    assert score.growth_gap == 80
    assert score.priority_band in {"high", "critical"}
    assert score.recommendation in {"prioritize_learning", "certification_candidate"}
    assert score.supporting_terms == ("databricks", "lakehouse")


def test_capability_gap_without_market_support_can_still_monitor_high_direction_gap() -> None:
    skill = CandidateSkill("Kafka", "data_engineering", capability_score=10, career_direction_weight=95)
    score = score_capability_gap(
        profile_name="Jens Career Transition",
        profile_version="v1",
        skill=skill,
        supports=[],
    )

    assert score.growth_gap == 85
    assert score.market_signal_score == Decimal("0.0")
    assert score.priority_score > Decimal("50.0")
    assert score.recommendation in {"practice_in_project", "prioritize_learning"}


def test_build_capability_gap_scores_groups_term_supports_by_skill() -> None:
    skills = [
        CandidateSkill("Cloud Data Platforms", "cloud", 35, 95),
        CandidateSkill("Product Ownership", "product", 90, 40),
    ]
    scores = build_capability_gap_scores(
        profile_name="Jens Career Transition",
        profile_version="v1",
        skills=skills,
        term_supports=[
            SearchTermSupport("cloud", "Cloud Data Platforms", Decimal("80.00"), "high"),
            SearchTermSupport("platform", "Cloud Data Platforms", Decimal("75.00"), "high"),
            SearchTermSupport("product", "Product Ownership", Decimal("40.00"), "low"),
        ],
    )

    assert scores[0].skill_name == "Cloud Data Platforms"
    assert scores[0].supporting_terms == ("cloud", "platform")
    assert all(score.skill_name != "Product Ownership" for score in scores)
