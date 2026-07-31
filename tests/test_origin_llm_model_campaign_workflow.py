from pathlib import Path


WORKFLOW = Path(".github/workflows/reusable-origin-llm-model-campaign.yml")


def test_model_campaign_workflow_is_bounded_and_review_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "name: Reusable origin LLM model campaign" in text
    assert "gpt-5.4-mini,gpt-5.6-terra,gpt-5.5" in text
    assert "benchmark_max_requests" in text
    assert "default: 18" in text
    assert "benchmark_max_estimated_cost_usd" in text
    assert "default: 0.50" in text
    assert "Provider disagreement: `manual review required`" in text
    assert "review_output_only_not_pipeline_input" in text
    assert "openai_api_key:" in text
    assert "required: true" in text


def test_evidence_stage_never_runs_single_model_adjudication() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "enable_llm_adjudication: false" in text
    assert "max_llm_adjudication_requests: 0" in text
    assert "scripts.run_origin_llm_model_campaign" in text
    assert "scripts.run_origin_llm_escalation" in text
