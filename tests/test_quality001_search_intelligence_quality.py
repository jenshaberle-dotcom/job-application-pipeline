from __future__ import annotations


from src.search_intelligence.market_sensor_funnel import ConnectorCandidate, MarketSensorItem
from src.search_intelligence.quality001_search_intelligence_quality import (
    bootstrap_assumption_inventory,
    build_quality001_report,
    quality001_safety_boundary,
    review_market_funnel_quality,
    review_sensor_effectiveness,
    review_stepstone_novelty,
)
from src.search_intelligence.stepstone_company_discovery_cycle import StepStoneDiscoveryAssessment


def test_quality001_safety_boundary_is_read_only() -> None:
    boundary = quality001_safety_boundary()

    assert boundary["read_only_quality_review"] is True
    assert boundary["external_requests"] is False
    assert boundary["database_writes"] is False
    assert boundary["candidate_or_gate_mutation"] is False
    assert boundary["connector_activation"] is False
    assert boundary["bronze_silver_gold_mutation"] is False
    assert boundary["scheduler_mutation"] is False


def test_sensor_effectiveness_detects_duplicate_dominated_ba_remote_runs() -> None:
    review = review_sensor_effectiveness(
        {
            "overall_status": "monitoring_attention_required_duplicate_dominated",
            "metric_summary": {
                "ingestion_run_count": 2,
                "total_loaded": 20,
                "inserted_count": 0,
                "duplicate_count": 20,
                "failed_run_count": 0,
                "observed_terms": ["Data Engineer"],
                "silent_terms": [],
            },
        }
    )

    assert review.effectiveness_level == "duplicate_dominated"
    assert review.inserted_share_percent == 0.0
    assert review.duplicate_share_percent == 100.0
    assert review.findings[0].severity == "high"
    assert review.findings[0].finding_id == "SENSOR-001I-003"


def test_market_funnel_quality_detects_promotion_gap() -> None:
    market_items = [
        MarketSensorItem(
            item_id=1,
            company_key="bahlsen",
            company_name="Bahlsen",
            source_name="manual_market_observation",
            decision="create_candidate_recommended",
            priority=90,
            evidence_count=3,
        ),
        MarketSensorItem(
            item_id=2,
            company_key="hdi",
            company_name="HDI",
            source_name="manual_market_observation",
            decision="already_known",
            priority=70,
            evidence_count=2,
        ),
    ]
    connector_candidates = [
        ConnectorCandidate(candidate_id=10, company_key="hdi", company_name="HDI", status="active_controlled")
    ]

    review = review_market_funnel_quality(market_items, connector_candidates)

    assert review.market_sensor_companies == 2
    assert review.with_connector_candidate == 1
    assert review.without_connector_candidate == 1
    assert review.promotion_gap_count == 1
    assert review.high_priority_gap_count == 1
    assert review.funnel_quality_level == "promotion_gap_visible"
    assert review.findings[0].severity == "high"


def test_stepstone_novelty_detects_known_company_dominated_cycle() -> None:
    assessment = StepStoneDiscoveryAssessment(
        search_term="Data Engineer",
        observed_count=10,
        distinct_company_count=4,
        known_cooldown_hit_count=6,
        new_company_count=2,
        relevance_hits=7,
        drift_hits=1,
        quality_score=0.4,
        recommended_interval_days=4,
        cooldown_proposals=(),
        reason="test",
    )

    review = review_stepstone_novelty(assessment)

    assert review.known_company_share_percent == 60.0
    assert review.novelty_share_percent == 50.0
    assert review.saturation_level == "known_company_dominated"
    assert review.findings[0].finding_id == "STEPSTONE-002A-003"


def test_build_quality001_report_combines_parallel_reviews_and_assumption_inventory() -> None:
    report = build_quality001_report(
        sensor001h_report={
            "overall_status": "monitoring_ready_with_observed_runs",
            "metric_summary": {
                "ingestion_run_count": 1,
                "total_loaded": 10,
                "inserted_count": 8,
                "duplicate_count": 2,
                "failed_run_count": 0,
                "observed_terms": ["Analytics Engineer"],
            },
        },
        market_items=[
            MarketSensorItem(
                item_id=1,
                company_key="getec",
                company_name="GETEC",
                source_name="manual_market_observation",
                decision="manual_review_required",
                priority=75,
                evidence_count=2,
            )
        ],
        connector_candidates=[],
        stepstone_assessments=[
            StepStoneDiscoveryAssessment(
                search_term="Analytics Engineer",
                observed_count=5,
                distinct_company_count=5,
                known_cooldown_hit_count=0,
                new_company_count=5,
                relevance_hits=4,
                drift_hits=0,
                quality_score=0.85,
                recommended_interval_days=2,
                cooldown_proposals=(),
                reason="test",
            )
        ],
    ).as_dict()

    assert report["schema_version"] == "quality001.search_intelligence_quality.v1"
    assert report["sensor_effectiveness"]["effectiveness_level"] == "observed_incremental_yield"
    assert report["market_funnel_quality"]["manual_review_gap_count"] == 1
    assert report["stepstone_novelty_reviews"][0]["saturation_level"] == "novelty_signal_visible"
    assert len(report["assumption_inventory"]) == len(bootstrap_assumption_inventory())
    assert report["safety_boundary"]["read_only_quality_review"] is True
