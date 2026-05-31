from src.search_intelligence.false_negative_risk import FalseNegativeRiskAssessment
from src.search_intelligence.search_term_learning import (
    build_reassessment_queue_items,
    build_search_term_suggestions,
    reassessment_priority,
)


def assessment(**overrides):
    data = {
        "candidate_id": 2,
        "company_key": "hdi",
        "company_name": "HDI Group",
        "risk_level": "high",
        "sighting_count": 3,
        "recent_sighting_count": 2,
        "last_observed_at": "2026-05-31T07:01:21+00:00",
        "reason": "unresolved employer-origin candidate still appears in market evidence",
        "suggested_search_terms": ("analytics", "business intelligence"),
        "evidence_sources": ("linkedin",),
        "evidence_titles": ("Data & Analytics Engineer",),
    }
    data.update(overrides)
    return FalseNegativeRiskAssessment(**data)


def test_builds_search_term_suggestions_from_actionable_false_negative_risk() -> None:
    suggestions = build_search_term_suggestions([assessment()])

    assert [item.suggested_term for item in suggestions] == [
        "analytics",
        "business intelligence",
    ]
    assert suggestions[0].company_key == "hdi"
    assert suggestions[0].risk_level == "high"


def test_low_risk_without_sightings_does_not_create_reassessment_work() -> None:
    items = build_reassessment_queue_items([
        assessment(risk_level="low", sighting_count=0, recent_sighting_count=0)
    ])

    assert items == []


def test_reassessment_priority_uses_risk_and_recent_sightings() -> None:
    assert reassessment_priority("critical", 5) > reassessment_priority("high", 5)
    assert reassessment_priority("high", 2) > reassessment_priority("medium", 2)


def test_builds_reassessment_item_with_terms_and_reason() -> None:
    items = build_reassessment_queue_items([assessment()])

    assert len(items) == 1
    assert items[0].company_name == "HDI Group"
    assert items[0].priority > 75
    assert "analytics" in items[0].suggested_search_terms
