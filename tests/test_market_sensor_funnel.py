from src.search_intelligence.market_sensor_funnel import (
    ConnectorCandidate,
    MarketSensorItem,
    companies_without_connector_candidate,
    count_market_companies_by_decision,
    summarize_funnel,
)


def market_item(
    company_key: str,
    decision: str = "create_candidate_recommended",
    *,
    priority: int = 100,
    evidence_count: int = 3,
) -> MarketSensorItem:
    return MarketSensorItem(
        item_id=1,
        company_key=company_key,
        company_name=company_key.replace("_", " ").title(),
        source_name="stepstone",
        decision=decision,
        priority=priority,
        evidence_count=evidence_count,
        distinct_search_term_count=2,
        sample_title_count=1,
        recommended_next_action="Review origin candidate creation",
    )


def connector(company_key: str, status: str = "discovery") -> ConnectorCandidate:
    return ConnectorCandidate(
        candidate_id=42,
        company_key=company_key,
        company_name=company_key.replace("_", " ").title(),
        status=status,
    )


def test_summarize_funnel_counts_distinct_companies() -> None:
    items = [
        market_item("adesso"),
        market_item("adesso", evidence_count=1),
        market_item("ratiodata"),
        market_item("deutsche_bahn"),
    ]
    candidates = [connector("adesso"), connector("hdi", status="active_controlled")]

    summary = summarize_funnel(items, candidates)

    assert summary.market_sensor_companies == 3
    assert summary.connector_candidate_companies == 2
    assert summary.with_connector_candidate == 1
    assert summary.without_connector_candidate == 2
    assert summary.connector_candidate_share_percent == 33.33


def test_companies_without_connector_candidate_prioritizes_promotion_gaps() -> None:
    items = [
        market_item("low_signal", decision="insufficient_evidence", priority=1, evidence_count=1),
        market_item("promotable", decision="create_candidate_recommended", priority=10, evidence_count=5),
        market_item("review_me", decision="manual_review_required", priority=99, evidence_count=4),
        market_item("known_company", decision="create_candidate_recommended", priority=100, evidence_count=9),
    ]
    candidates = [connector("known_company")]

    gaps = companies_without_connector_candidate(items, candidates)

    assert [gap.company_key for gap in gaps] == ["promotable", "review_me", "low_signal"]
    assert gaps[0].suggested_funnel_action == "promotion_gap_create_candidate_recommended"
    assert gaps[1].suggested_funnel_action == "promotion_gap_manual_review_required"
    assert gaps[2].suggested_funnel_action == "observe_more_before_promotion"


def test_market_companies_by_decision_uses_schema_decision_not_review_status() -> None:
    counts = count_market_companies_by_decision(
        [
            market_item("a", decision="create_candidate_recommended"),
            market_item("b", decision="manual_review_required"),
            market_item("b", decision="manual_review_required"),
        ]
    )

    assert counts == {
        "create_candidate_recommended": 1,
        "manual_review_required": 1,
    }
