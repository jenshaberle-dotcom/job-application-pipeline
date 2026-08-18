from __future__ import annotations

import json

from src.search_intelligence.llm_booster_policy import BoosterStage
from src.search_intelligence.product_v1_assessment_evidence import (
    extract_product_v1_assessment_evidence,
)
from src.search_intelligence.product_v1_ranking_booster import (
    RankingHypothesisObservation,
    execute_product_v1_ranking_booster,
    request_product_v1_ranking_hypotheses,
)
from src.search_intelligence.product_v1_ranking_evidence import (
    RankingSignalReference,
    build_product_v1_ranking_evidence,
)


URL = "https://jobs.example.com/jobs/ranking-booster-1"


def _assessment(description: str, title: str):
    return extract_product_v1_assessment_evidence(
        description=description,
        title=title,
        source_url=URL,
    )


def _ranking(description: str, title: str):
    return build_product_v1_ranking_evidence(
        title=title,
        description=description,
        origin_validation_status="validated",
        activity_status="active",
        assessment_evidence=_assessment(description, title),
    )


def _response(hypotheses: list[dict[str, str]]):
    return {
        "id": "resp_ranking_test",
        "model": "gpt-5.6-luna",
        "output_text": json.dumps({"hypotheses": hypotheses, "rationale": "quoted"}),
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }


def test_provider_accepts_only_controlled_exact_quote_signals() -> None:
    detail = "Design resilient services with high availability for customer workloads."
    payloads: list[dict[str, object]] = []

    def transport(_url, _headers, payload, _timeout):
        payloads.append(dict(payload))
        return _response(
            [
                {
                    "factor": "reliability_focus",
                    "signal": "resilience_context",
                    "evidence": "resilient services",
                },
                {
                    "factor": "reliability_focus",
                    "signal": "availability_context",
                    "evidence": "high availability",
                },
            ]
        )

    observation = request_product_v1_ranking_hypotheses(
        company_name="Example",
        detail_url=URL,
        title="Data Engineer",
        detail_text=detail,
        requested_factors=("reliability_focus",),
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )

    assert observation.status == "completed"
    assert [(reference.signal, reference.points) for reference in observation.references] == [
        ("resilience_context", 20.0),
        ("availability_context", 20.0),
    ]
    for reference in observation.references:
        assert detail[reference.span_start : reference.span_end] == reference.evidence
        assert reference.source_surface == "description"

    schema = payloads[0]["text"]["format"]["schema"]
    item_properties = schema["properties"]["hypotheses"]["items"]["properties"]
    assert set(item_properties) == {"factor", "signal", "evidence"}
    assert "score" not in item_properties
    assert "rank" not in item_properties
    assert "top5" not in item_properties


def test_provider_rejects_signal_factor_mismatch() -> None:
    detail = "The platform requires high availability."

    def transport(_url, _headers, _payload, _timeout):
        return _response(
            [
                {
                    "factor": "data_focus",
                    "signal": "availability_context",
                    "evidence": "high availability",
                }
            ]
        )

    observation = request_product_v1_ranking_hypotheses(
        company_name="Example",
        detail_url=URL,
        title="Data Engineer",
        detail_text=detail,
        requested_factors=("data_focus",),
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )

    assert observation.status == "failed_closed"
    assert observation.references == ()


def test_model_context_adds_only_fixed_deterministic_points() -> None:
    title = "Data Engineer"
    description = "Build data pipelines with SQL. Design resilient services with high availability."
    deterministic = _ranking(description, title)
    assert deterministic.profile_direction_score == 85
    assert deterministic.data_focus_score == 50
    assert deterministic.reliability_focus_score == 0

    resilience_start = description.index("resilient services")
    availability_start = description.index("high availability")
    calls: list[BoosterStage] = []

    def model(stage, _requested):
        calls.append(stage)
        if stage == BoosterStage.LUNA_MEDIUM:
            return RankingHypothesisObservation(
                status="completed",
                request_attempted=True,
                references=(
                    RankingSignalReference(
                        factor="reliability_focus",
                        signal="resilience_context",
                        source_surface="description",
                        evidence="resilient services",
                        span_start=resilience_start,
                        span_end=resilience_start + len("resilient services"),
                        points=20.0,
                    ),
                    RankingSignalReference(
                        factor="reliability_focus",
                        signal="availability_context",
                        source_surface="description",
                        evidence="high availability",
                        span_start=availability_start,
                        span_end=availability_start + len("high availability"),
                        points=20.0,
                    ),
                ),
                estimated_cost_usd=0.001,
            )
        return RankingHypothesisObservation(
            status="completed",
            request_attempted=True,
            references=(),
            estimated_cost_usd=0.001,
        )

    execution = execute_product_v1_ranking_booster(
        deterministic_evidence=deterministic,
        model=model,
    )

    assert calls == [
        BoosterStage.LUNA_MEDIUM,
        BoosterStage.TERRA_MEDIUM,
        BoosterStage.SOL_MEDIUM,
        BoosterStage.LUNA_MAX,
    ]
    assert execution.profile_direction_score == 85
    assert execution.data_focus_score == 50
    assert execution.reliability_focus_score == 40
    assert execution.evidence_quality_score == deterministic.evidence_quality_score
    assert execution.provider_requests == 4
    assert execution.llm_requests == 4
    assert execution.tavily_requests == 0
    assert execution.database_writes == 0
    assert execution.ranking_writes == 0
    assert execution.top5_writes == 0
    assert execution.application_writes == 0
    assert execution.product_writes == 0
    assert execution.ranking_authority is False
    assert execution.top5_authority is False
    assert execution.product_authority is False


def test_saturated_deterministic_fit_skips_all_models() -> None:
    title = "Data Engineer"
    description = (
        "Permanent employment. Hybrid work model. Fluent German and English. 35-40 hours per week. "
        "We require a senior-level professional. Machine learning MLOps Generative AI LLM PyTorch. "
        "Data pipelines SQL Spark Databricks lakehouse ETL. Reliability test automation observability "
        "CI/CD production systems Terraform."
    )
    deterministic = _ranking(description, title)
    assert deterministic.profile_direction_score == 100
    assert deterministic.data_focus_score == 100
    assert deterministic.reliability_focus_score == 100

    def model(_stage, _requested):
        raise AssertionError("model must not run for saturated deterministic fit evidence")

    execution = execute_product_v1_ranking_booster(
        deterministic_evidence=deterministic,
        model=model,
    )

    assert execution.requested_factors == ()
    assert execution.unresolved_factors == ()
    assert execution.provider_requests == 0
    assert all(not stage.attempted for stage in execution.stages[1:])


def test_execution_rejects_model_ranking_authority_claim() -> None:
    deterministic = _ranking("Build data pipelines with SQL.", "Data Engineer")

    def model(_stage, _requested):
        return RankingHypothesisObservation(
            status="completed",
            request_attempted=True,
            references=(),
            estimated_cost_usd=0.001,
            ranking_authority=True,
        )

    execution = execute_product_v1_ranking_booster(
        deterministic_evidence=deterministic,
        model=model,
    )

    luna = execution.stages[2]
    assert luna.status == "failed_closed"
    assert luna.reason_code == "model_ranking_or_product_authority_claim_rejected"
    assert execution.score_patch() == deterministic.ranking_scores_patch()
    payload = execution.to_json()
    assert "rank" not in payload
    assert "top5_membership" not in payload
    assert payload["ranking_authority"] is False
    assert payload["top5_authority"] is False
    assert payload["product_authority"] is False
