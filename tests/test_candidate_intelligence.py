from __future__ import annotations

import pytest

from src.search_intelligence.candidate_intelligence import (
    DEFAULT_PROFILE,
    DEFAULT_SKILLS,
    CandidateSkill,
    profile_summary,
    top_growth_areas,
    top_strengths,
    transition_assets,
    validate_skill,
)


def test_default_profile_targets_data_engineering_transition() -> None:
    assert DEFAULT_PROFILE.profile_name == "Jens Career Transition"
    assert DEFAULT_PROFILE.target_role == "Data Engineer"
    assert DEFAULT_PROFILE.profile_version == "v1"


def test_top_strengths_prefer_current_capability() -> None:
    strengths = top_strengths(DEFAULT_SKILLS, limit=3)

    assert [skill.skill_name for skill in strengths] == [
        "Requirements Engineering",
        "Stakeholder Management",
        "Product Ownership",
    ]
    assert [skill.capability_score for skill in strengths] == sorted(
        [skill.capability_score for skill in strengths],
        reverse=True,
    )


def test_top_growth_areas_prefer_high_direction_and_large_gap() -> None:
    growth = top_growth_areas(DEFAULT_SKILLS, limit=4)

    assert [skill.skill_name for skill in growth] == [
        "Spark",
        "Kafka",
        "Databricks",
        "Cloud Data Platforms",
    ]


def test_transition_assets_are_skills_with_capability_and_direction() -> None:
    assets = transition_assets(DEFAULT_SKILLS, limit=5)
    names = [skill.skill_name for skill in assets]

    assert "SQL" in names
    assert "Python" in names
    assert "PostgreSQL" in names
    assert "Requirements Engineering" not in names


def test_profile_summary_exposes_strengths_assets_and_growth_areas() -> None:
    summary = profile_summary(DEFAULT_SKILLS)

    assert set(summary) == {"strengths", "transition_assets", "growth_areas"}
    assert summary["strengths"]
    assert summary["transition_assets"]
    assert summary["growth_areas"]


def test_validate_skill_rejects_invalid_scores() -> None:
    with pytest.raises(ValueError):
        validate_skill(CandidateSkill("Impossible", "test", 101, 50))

    with pytest.raises(ValueError):
        validate_skill(CandidateSkill("Impossible", "test", 50, -1))
