from scripts.aggregator_discovery_policy import AggregatorSuppressionDecision
from scripts.run_aggregator_discovery_suppression_agent import (
    DECISION_SCOPE,
    decision_summary,
    summarize_decisions,
)


def test_decision_summary_counts_suppression_and_recheck() -> None:
    decisions = [
        AggregatorSuppressionDecision(
            aggregator_source_name="stepstone",
            company="Finanz Informatik",
            normalized_company_key="finanz_informatik",
            decision="suppress_active_connector_candidate",
            reason="already active",
            silver_job_count=2,
        ),
        AggregatorSuppressionDecision(
            aggregator_source_name="stepstone",
            company="HDI",
            normalized_company_key="hdi",
            decision="suppress_known_connector_candidate",
            reason="known candidate",
            silver_job_count=1,
            recheck_eligible=True,
            recheck_reason="inactive candidate is due for lifecycle review",
        ),
        AggregatorSuppressionDecision(
            aggregator_source_name="stepstone",
            company="New Employer",
            normalized_company_key="new_employer",
            decision="keep_for_discovery_review",
            reason="unknown company",
            silver_job_count=1,
        ),
    ]

    assert decision_summary(decisions) == {
        "company_count": 3,
        "suppressed_count": 2,
        "kept_for_discovery_review_count": 1,
        "recheck_eligible_known_candidate_count": 1,
    }


def test_summarize_decisions_prints_handoff_action_and_observation_counts() -> None:
    decision = AggregatorSuppressionDecision(
        aggregator_source_name="stepstone",
        company="HDI",
        normalized_company_key="hdi",
        decision="suppress_known_connector_candidate",
        reason="known candidate",
        silver_job_count=4,
        first_seen_at="2026-05-01T00:00:00+00:00",
        last_seen_at="2026-05-30T00:00:00+00:00",
        known_candidate_id=5,
        known_candidate_status="manual_review_required",
        known_candidate_source_name="hdi:career",
        recheck_eligible=True,
        recheck_reason="due for lifecycle review",
    )

    output = "\n".join(summarize_decisions([decision]))

    assert "silver_job_count: 4" in output
    assert "handoff_action: queue_employer_origin_recheck" in output
    assert "known_candidate_source_name: hdi:career" in output


def test_decision_scope_documents_stepstone_known_candidate_suppression() -> None:
    assert DECISION_SCOPE == "stepstone_known_candidate_suppression"
