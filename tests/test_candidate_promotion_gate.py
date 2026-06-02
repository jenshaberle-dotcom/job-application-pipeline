from src.search_intelligence.candidate_promotion import (
    CandidateExpansionItem,
    build_candidate_promotion_review,
    decide_candidate_promotion_item,
)


def item(decision: str, known_candidate_id: int | None = None) -> CandidateExpansionItem:
    return CandidateExpansionItem(
        item_id=1,
        review_id=7,
        company_key="ratiodata",
        company_name="Ratiodata SE",
        source_name="stepstone",
        decision=decision,
        priority=100,
        evidence_count=4,
        known_candidate_id=known_candidate_id,
        recommended_next_action="Review candidate creation",
        reason="test evidence",
    )


def test_create_candidate_recommended_becomes_promotion_recommended() -> None:
    decision = decide_candidate_promotion_item(item("create_candidate_recommended"))

    assert decision.promotion_decision == "promotion_recommended"
    assert decision.candidate_url is None
    assert decision.source_name_candidate == "ratiodata:discovery"
    assert decision.source_family_candidate == "ratiodata"
    assert decision.recommended_next_action == "Create discovery candidate, then run Origin Source Discovery Gate"


def test_manual_review_does_not_directly_promote() -> None:
    decision = decide_candidate_promotion_item(item("manual_review_required"))

    assert decision.promotion_decision == "promotion_manual_review_required"
    assert decision.risk_level == "medium"


def test_known_candidate_is_skipped() -> None:
    decision = decide_candidate_promotion_item(item("create_candidate_recommended", known_candidate_id=42))

    assert decision.promotion_decision == "promotion_skipped_existing"
    assert decision.risk_level == "low"


def test_build_review_counts_and_filter() -> None:
    items = [
        item("create_candidate_recommended"),
        CandidateExpansionItem(
            item_id=2,
            review_id=7,
            company_key="noise",
            company_name="Noise GmbH",
            source_name="stepstone",
            decision="suppress_as_noise",
            priority=1,
            evidence_count=1,
        ),
    ]

    review = build_candidate_promotion_review(items, candidate_expansion_review_id=7)

    assert review.item_count == 2
    assert review.promotion_recommended_count == 1
    assert review.rejected_count == 1

    filtered = build_candidate_promotion_review(items, candidate_expansion_review_id=7, company_key_filter="ratiodata")
    assert filtered.item_count == 1
    assert filtered.items[0].company_key == "ratiodata"
