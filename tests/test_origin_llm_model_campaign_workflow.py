from pathlib import Path


WORKFLOW = Path(".github/workflows/reusable-origin-llm-model-campaign.yml")


def test_model_campaign_workflow_is_call_bounded_and_review_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "name: Reusable origin LLM model campaign" in text
    assert "gpt-5.4-mini,gpt-5.6-terra,gpt-5.5" in text
    assert "benchmark_max_requests" in text
    assert "default: 18" in text
    assert "benchmark_max_requests must equal cases multiplied by model count" in text
    assert "benchmark_max_estimated_cost_usd:" not in text
    assert "escalation_max_estimated_cost_usd:" not in text
    assert text.count("--max-estimated-cost-usd inf") == 2
    assert "Cost telemetry: `reported but not used as a stop gate`" in text
    assert "Provider disagreement: `manual review required`" in text
    assert "review_output_only_not_pipeline_input" in text
    assert "openai_api_key:" in text
    assert "required: true" in text


def test_downloaded_evidence_artifact_is_resolved_recursively_and_uniquely() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Resolve immutable origin evidence input" in text
    assert 'root.rglob("origin-evidence-adjudication.json")' in text
    assert "expected exactly one origin-evidence-adjudication.json" in text
    assert text.count('${{ steps.evidence-input.outputs.path }}') == 2
    assert (
        '${{ runner.temp }}/origin-provider-artifact/origin-evidence-adjudication.json'
        not in text
    )


def test_evidence_stage_never_runs_single_model_adjudication() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "enable_llm_adjudication: false" in text
    assert "max_llm_adjudication_requests: 0" in text
    assert "scripts.run_origin_llm_model_campaign" in text
    assert "scripts.run_origin_llm_escalation" in text
