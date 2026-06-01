from decimal import Decimal

from src.search_intelligence.candidate_intelligence import DEFAULT_PROFILE, DEFAULT_SKILLS
from src.search_intelligence.search_term_value import (
    VocabularySignalInput,
    build_search_term_value_scores,
    build_vocabulary_signal_scores,
    match_skill_for_term,
    score_vocabulary_signal,
)


def test_noise_terms_are_penalized() -> None:
    useful = score_vocabulary_signal(VocabularySignalInput("analytics", company_count=4, observation_count=8))
    noisy = score_vocabulary_signal(VocabularySignalInput("mitarbeiter", company_count=4, observation_count=8))

    assert useful.signal_score > noisy.signal_score
    assert noisy.noise_penalty >= 80


def test_cross_company_signal_increases_score() -> None:
    narrow = score_vocabulary_signal(VocabularySignalInput("analytics", company_count=1, observation_count=3))
    broad = score_vocabulary_signal(VocabularySignalInput("analytics", company_count=8, observation_count=24))

    assert broad.signal_score > narrow.signal_score


def test_term_alias_matches_candidate_skill() -> None:
    assert match_skill_for_term("analytics", DEFAULT_SKILLS).skill_name == "Analytics"
    assert match_skill_for_term("platform", DEFAULT_SKILLS).skill_name == "Cloud Data Platforms"
    assert match_skill_for_term("requirements", DEFAULT_SKILLS).skill_name == "Requirements Engineering"


def test_search_term_value_prefers_data_engineering_direction() -> None:
    signals = build_vocabulary_signal_scores(
        [
            VocabularySignalInput("analytics", company_count=6, observation_count=12),
            VocabularySignalInput("requirements", company_count=6, observation_count=12),
        ]
    )
    scores = build_search_term_value_scores(
        signals,
        profile_name=DEFAULT_PROFILE.profile_name,
        profile_version=DEFAULT_PROFILE.profile_version,
        skills=DEFAULT_SKILLS,
    )
    by_term = {item.observed_term: item for item in scores}

    assert by_term["analytics"].career_direction_score > by_term["requirements"].career_direction_score
    assert by_term["analytics"].overall_value_score > by_term["requirements"].overall_value_score


def test_noisy_terms_remain_low_value_even_when_observed() -> None:
    signals = build_vocabulary_signal_scores(
        [
            VocabularySignalInput("mitarbeiter", company_count=10, observation_count=40),
        ]
    )
    scores = build_search_term_value_scores(
        signals,
        profile_name=DEFAULT_PROFILE.profile_name,
        profile_version=DEFAULT_PROFILE.profile_version,
        skills=DEFAULT_SKILLS,
    )

    assert scores[0].value_band == "low"
    assert scores[0].overall_value_score < Decimal("45.00")
