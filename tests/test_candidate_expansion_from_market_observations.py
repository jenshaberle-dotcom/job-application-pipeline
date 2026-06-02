from src.search_intelligence.candidate_expansion import (
    KnownCandidate,
    MarketCompanyObservation,
    build_candidate_expansion_review,
    decide_candidate_expansion_item,
)


def test_recommends_candidate_creation_for_repeated_data_observations() -> None:
    item = decide_candidate_expansion_item(
        MarketCompanyObservation(
            company_key="ratiodata",
            company_name="Ratiodata SE",
            source_name="stepstone",
            observation_count=4,
            latest_observed_at="2026-06-01T00:00:00+00:00",
            search_terms=("Data Engineer",),
            sample_titles=("M365 System Engineer", "Data Platform Engineer"),
        ),
        [],
    )

    assert item.decision == "create_candidate_recommended"
    assert item.recommended_next_action == "Review candidate creation, then run Origin Source Discovery Gate"
    assert item.evidence["data_search_terms"] == ["data engineer"]


def test_routes_existing_candidate_without_duplicate_creation() -> None:
    item = decide_candidate_expansion_item(
        MarketCompanyObservation(
            company_key="hdi",
            company_name="HDI AG",
            source_name="stepstone",
            observation_count=9,
            latest_observed_at=None,
            search_terms=("Data Platform",),
            sample_titles=("Platform Engineer Azure",),
        ),
        [
            KnownCandidate(
                candidate_id=2,
                company_key="hdi",
                company_name="HDI Group",
                status="manual_review_required",
            )
        ],
    )

    assert item.decision == "already_known"
    assert item.known_candidate_id == 2


def test_build_review_counts_decision_groups() -> None:
    review = build_candidate_expansion_review(
        [
            MarketCompanyObservation(
                company_key="ratiodata",
                company_name="Ratiodata SE",
                source_name="stepstone",
                observation_count=4,
                latest_observed_at=None,
                search_terms=("Data Engineer",),
                sample_titles=("Data Platform Engineer",),
            ),
            MarketCompanyObservation(
                company_key="single_noise",
                company_name="Single Noise GmbH",
                source_name="stepstone",
                observation_count=1,
                latest_observed_at=None,
                search_terms=("ETL",),
                sample_titles=("Senior Prüfer (m/w/d)",),
            ),
        ],
        [],
    )

    assert review.company_count == 2
    assert review.create_recommended_count == 1
    assert review.suppressed_count == 1
    assert review.boundary["candidate_creation_allowed"] is False
