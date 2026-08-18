from __future__ import annotations

import json

from src.search_intelligence.llm_booster_policy import BoosterStage
from src.search_intelligence.product_v1_assessment_booster import (
    AssessmentHypothesisObservation,
    execute_product_v1_assessment_booster,
    openai_assessment_model_callback,
    request_product_v1_assessment_hypotheses,
)
from src.search_intelligence.product_v1_assessment_evidence import (
    AssessmentEvidenceReference,
    extract_product_v1_assessment_evidence,
)


URL = "https://jobs.example.com/jobs/assessment-1"
TITLE = "Senior Data Engineer"
DETAIL_TEXT = (
    "Permanent employment. We use a hybrid work model. "
    "Fluent German and English are required. The contract is 35-40 hours per week. "
    "We are looking for a senior-level professional."
)


def _response(hypotheses: list[dict[str, str]], *, model: str = "gpt-5.6-luna"):
    return {
        "id": "resp_test",
        "model": model,
        "output_text": json.dumps({"hypotheses": hypotheses, "rationale": "quoted"}),
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }


def test_provider_returns_only_deterministically_parsed_quote_evidence() -> None:
    seen_payloads: list[dict[str, object]] = []

    def transport(_url, _headers, payload, _timeout):
        seen_payloads.append(dict(payload))
        return _response(
            [
                {"field": "employment_type", "evidence": "Permanent employment"},
                {"field": "required_languages", "evidence": "Fluent German and English"},
                {"field": "weekly_hours", "evidence": "35-40 hours per week"},
                {"field": "work_model", "evidence": "hybrid work model"},
                {
                    "field": "requirements_seniority",
                    "evidence": "senior-level professional",
                },
            ]
        )

    observation = request_product_v1_assessment_hypotheses(
        company_name="Example",
        detail_url=URL,
        title=TITLE,
        detail_text=DETAIL_TEXT,
        requested_fields=(
            "employment_type",
            "required_languages",
            "weekly_hours",
            "work_model",
            "requirements_seniority",
        ),
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )

    assert observation.status == "completed"
    assert observation.field_values == {
        "employment_type": "permanent",
        "required_languages": ("de", "en"),
        "weekly_hours": (35.0, 40.0),
        "work_model": "hybrid",
        "requirements_seniority": "senior",
    }
    assert observation.product_authority is False
    assert observation.evidence_references
    assert all(reference.source_url == URL for reference in observation.evidence_references)
    assert all(
        DETAIL_TEXT[reference.span_start : reference.span_end] == reference.evidence
        for reference in observation.evidence_references
    )

    schema = seen_payloads[0]["text"]["format"]["schema"]
    hypothesis_properties = schema["properties"]["hypotheses"]["items"]["properties"]
    assert set(hypothesis_properties) == {"field", "evidence"}


def test_provider_rejects_experience_only_seniority_quote() -> None:
    detail = "You bring 8 years of professional experience in data engineering."

    def transport(_url, _headers, _payload, _timeout):
        return _response(
            [
                {
                    "field": "requirements_seniority",
                    "evidence": "8 years of professional experience",
                }
            ]
        )

    observation = request_product_v1_assessment_hypotheses(
        company_name="Example",
        detail_url=URL,
        title="Data Engineer",
        detail_text=detail,
        requested_fields=("requirements_seniority",),
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )

    assert observation.status == "failed_closed"
    assert observation.field_values == {}
    assert observation.evidence_references == ()
    assert observation.product_authority is False


def test_deterministic_completion_skips_entire_model_cascade() -> None:
    deterministic = extract_product_v1_assessment_evidence(
        description=DETAIL_TEXT,
        title=TITLE,
        source_url=URL,
    )

    def model(_stage, _requested):
        raise AssertionError("model must not run after deterministic completion")

    execution = execute_product_v1_assessment_booster(
        deterministic_evidence=deterministic,
        model=model,
    )

    assert execution.requested_fields == ()
    assert execution.unresolved_fields == ()
    assert execution.provider_requests == 0
    assert execution.llm_requests == 0
    assert execution.tavily_requests == 0
    assert [stage.stage for stage in execution.stages] == [
        BoosterStage.DETERMINISTIC,
        BoosterStage.TAVILY,
        BoosterStage.LUNA_MEDIUM,
        BoosterStage.TERRA_MEDIUM,
        BoosterStage.SOL_MEDIUM,
        BoosterStage.LUNA_MAX,
        BoosterStage.DEEP_EVIDENCE,
    ]
    assert all(not stage.attempted for stage in execution.stages[1:])
    assert execution.hard_filter_authority is False
    assert execution.product_authority is False


def test_luna_quote_can_fill_residuals_but_never_hard_filter_or_product_authority() -> None:
    deterministic = extract_product_v1_assessment_evidence(
        description="Join our data platform team.",
        title="Data Engineer",
        source_url=URL,
    )
    detail = DETAIL_TEXT
    calls: list[BoosterStage] = []

    def transport(_url, _headers, _payload, _timeout):
        return _response(
            [
                {"field": "employment_type", "evidence": "Permanent employment"},
                {"field": "required_languages", "evidence": "Fluent German and English"},
                {"field": "weekly_hours", "evidence": "35-40 hours per week"},
                {"field": "work_model", "evidence": "hybrid work model"},
                {
                    "field": "requirements_seniority",
                    "evidence": "senior-level professional",
                },
            ]
        )

    bound = openai_assessment_model_callback(
        company_name="Example",
        detail_url=URL,
        title=TITLE,
        detail_text=detail,
        api_key="test-key",
        transport=transport,
    )

    def model(stage, requested):
        calls.append(stage)
        return bound(stage, requested)

    execution = execute_product_v1_assessment_booster(
        deterministic_evidence=deterministic,
        model=model,
    )

    assert calls == [BoosterStage.LUNA_MEDIUM]
    assert execution.provider_requests == 1
    assert execution.llm_requests == 1
    assert execution.tavily_requests == 0
    assert execution.unresolved_fields == ()
    assert execution.assessment_patch["employment_type"] == "permanent"
    assert execution.assessment_patch["required_languages"] == ["de", "en"]
    assert execution.assessment_patch["weekly_hours_min"] == 35
    assert execution.assessment_patch["weekly_hours_max"] == 40
    assert execution.assessment_patch["work_model"] == "hybrid"
    assert execution.assessment_patch["requirements_seniority"] == "senior"
    assert execution.database_writes == 0
    assert execution.hard_filter_writes == 0
    assert execution.ranking_writes == 0
    assert execution.application_writes == 0
    assert execution.product_writes == 0
    assert execution.candidate_fact_authority is False
    assert execution.capability_fit_authority is False
    assert execution.hard_filter_authority is False
    assert execution.ranking_authority is False
    assert execution.product_authority is False


def test_execution_rejects_model_product_authority_claim() -> None:
    deterministic = extract_product_v1_assessment_evidence(
        description="Join our data platform team.",
        title="Data Engineer",
        source_url=URL,
    )
    reference = AssessmentEvidenceReference(
        field="employment_type",
        source_url=URL,
        observed_value="Permanent employment",
        canonical_value="permanent",
        evidence="Permanent employment",
        span_start=0,
        span_end=20,
    )

    def model(_stage, _requested):
        return AssessmentHypothesisObservation(
            status="completed",
            request_attempted=True,
            field_values={"employment_type": "permanent"},
            evidence_references=(reference,),
            estimated_cost_usd=0.001,
            product_authority=True,
        )

    execution = execute_product_v1_assessment_booster(
        deterministic_evidence=deterministic,
        model=model,
    )

    assert execution.assessment_patch["employment_type"] == "unknown"
    assert execution.unresolved_fields
    luna = execution.stages[2]
    assert luna.status == "failed_closed"
    assert luna.reason_code == "model_product_authority_claim_rejected"
    assert execution.product_authority is False
