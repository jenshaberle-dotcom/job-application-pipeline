from src.search_intelligence.false_negative_risk import (
    CandidateMarketEvidenceSummary,
    assess_false_negative_risk,
    suggested_search_terms_from_titles,
)


def summary(**overrides):
    data = {
        "candidate_id": 2,
        "company_key": "hdi",
        "company_name": "HDI Group",
        "candidate_status": "manual_review_required",
        "candidate_risk_level": "medium",
        "sighting_count": 3,
        "recent_sighting_count": 1,
        "last_observed_at": "2026-05-30T12:00:00+00:00",
        "evidence_sources": ("linkedin", "stepstone"),
        "evidence_titles": ("Data & Analytics Engineer",),
    }
    data.update(overrides)
    return CandidateMarketEvidenceSummary(**data)


def test_unresolved_candidate_with_recent_market_evidence_is_high_risk() -> None:
    assessment = assess_false_negative_risk(summary())

    assert assessment.risk_level == "high"
    assert assessment.company_key == "hdi"
    assert "analytics" in assessment.suggested_search_terms


def test_active_controlled_candidate_stays_low_risk() -> None:
    assessment = assess_false_negative_risk(
        summary(candidate_status="active_controlled", sighting_count=10, recent_sighting_count=5)
    )

    assert assessment.risk_level == "low"


def test_many_recent_unresolved_sightings_become_critical() -> None:
    assessment = assess_false_negative_risk(summary(sighting_count=8, recent_sighting_count=6))

    assert assessment.risk_level == "critical"


def test_suggested_search_terms_extracts_domain_language() -> None:
    terms = suggested_search_terms_from_titles([
        "Data & Analytics Engineer",
        "Business Intelligence Specialist",
        "Data Management Analyst",
    ])

    assert "analytics" in terms
    assert "business intelligence" in terms
    assert "data management" in terms
