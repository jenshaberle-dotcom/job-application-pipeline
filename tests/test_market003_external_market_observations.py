import pytest

from src.search_intelligence.market003_external_market_observations import (
    ManualMarketObservationInput,
    build_manual_market_observation_plan,
    build_manual_market_observation_review,
    market003_safety_boundary,
)


def test_market003_plan_flags_manual_observation_as_learning_signal_only() -> None:
    plan = build_manual_market_observation_plan(
        ManualMarketObservationInput(
            company_name="Bahlsen GmbH",
            title="Data Engineer",
            observation_channel="linkedin",
            evidence_url="https://example.test/job/1",
            search_term="data engineer",
            remote_signal="hybrid",
            relevance_signal="strong",
            note="Manual LinkedIn reality-check hit.",
        )
    )

    assert plan.insert_allowed is True
    assert plan.company_key == "bahlsen"
    assert plan.evidence_kind == "manual_market_observation"
    assert plan.source_name == "linkedin"
    assert plan.action == "insert_manual_market_observation"
    assert plan.evidence_payload["input_mode"] == "manual_market_observation"
    assert plan.evidence_payload["decision_boundary"] == "learning_signal_only_not_gate_truth"
    assert plan.evidence_payload["boundary"]["candidate_creation"] is False
    assert plan.evidence_payload["boundary"]["source_activation"] is False


def test_market003_rejects_unknown_channel_before_persistence() -> None:
    with pytest.raises(ValueError, match="Unsupported observation_channel"):
        build_manual_market_observation_plan(
            ManualMarketObservationInput(
                company_name="Example AG",
                title="Analytics Engineer",
                observation_channel="random_csv_import",
            )
        )


def test_market003_review_counts_companies_channels_and_signals() -> None:
    review = build_manual_market_observation_review(
        [
            {
                "normalized_company_key": "bahlsen",
                "source_name": "linkedin",
                "evidence": {"relevance_signal": "strong", "remote_signal": "hybrid"},
            },
            {
                "normalized_company_key": "getec",
                "source_name": "recruiter",
                "evidence": {"relevance_signal": "medium", "remote_signal": "remote_possible"},
            },
            {
                "normalized_company_key": "bahlsen",
                "source_name": "linkedin",
                "evidence": {"relevance_signal": "strong", "remote_signal": "hybrid"},
            },
        ]
    )

    assert review.observation_count == 3
    assert review.distinct_company_count == 2
    assert review.channel_counts == {"linkedin": 2, "recruiter": 1}
    assert review.relevance_counts == {"medium": 1, "strong": 2}
    assert review.remote_signal_counts == {"hybrid": 2, "remote_possible": 1}
    assert review.strong_relevant_company_count == 1
    assert review.as_dict()["next_action"] == "run_candidate_expansion_review_without_automatic_promotion"


def test_market003_safety_boundary_excludes_pipeline_mutation() -> None:
    boundary = market003_safety_boundary()

    assert boundary["manual_market_observation_only"] is True
    assert boundary["dry_run_by_default"] is True
    assert boundary["database_write_requires_explicit_write_flag"] is True
    assert boundary["database_write_scope_market_evidence_only"] is True
    assert boundary["job_ingestion"] is False
    assert boundary["bronze_write"] is False
    assert boundary["silver_gold_mutation"] is False
    assert boundary["candidate_creation"] is False
    assert boundary["gate_decision"] is False
    assert boundary["connector_build_or_registration"] is False
    assert boundary["csv_or_export_as_pipeline_input"] is False
