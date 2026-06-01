
from src.search_intelligence.company_vocabulary import (
    MarketEvidenceVocabularyInput,
    build_company_vocabulary_observations,
    extract_vocabulary_terms,
)


def test_extracts_analytics_from_data_analytics_title() -> None:
    assert "analytics" in extract_vocabulary_terms("Data & Analytics Engineer")


def test_extracts_agentic_ai_platform_terms() -> None:
    terms = extract_vocabulary_terms("Agentic AI Platform Engineer")
    assert "agentic" in terms
    assert "ai" in terms
    assert "platform" in terms
    assert "engineer" not in terms


def test_builds_company_vocabulary_observations_grouped_by_company_term_and_source() -> None:
    observations = build_company_vocabulary_observations(
        [
            MarketEvidenceVocabularyInput(
                company_key="hdi",
                company_name="HDI Group",
                title="Data & Analytics Engineer",
                source_name="linkedin",
                observed_at="2026-05-31T10:00:00+00:00",
            ),
            MarketEvidenceVocabularyInput(
                company_key="hdi",
                company_name="HDI Group",
                title="Senior Analytics Platform Engineer",
                source_name="linkedin",
                observed_at="2026-05-31T11:00:00+00:00",
            ),
        ]
    )

    analytics = [item for item in observations if item.observed_term == "analytics"]
    assert len(analytics) == 1
    assert analytics[0].company_key == "hdi"
    assert analytics[0].observation_count == 2
