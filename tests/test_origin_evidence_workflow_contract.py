from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "reusable-origin-provider-benchmark.yml"
CALLER = ROOT / "docs" / "reference" / "security" / "private_origin_runtime_caller.example.yml"


def test_reusable_workflow_keeps_llm_disabled_by_default() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "enable_llm_adjudication:" in text
    assert "default: false" in text
    assert "max_llm_adjudication_requests:" in text
    assert "openai_api_key:" in text
    assert "required: false" in text
    assert "python -m scripts.run_origin_evidence_adjudication" in text


def test_evidence_step_runs_after_runtime_lease_release() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    release = text.index("- name: Release local runtime lease")
    evidence = text.index("- name: Grade source evidence and adjudicate unresolved cases")
    success_marker = text.index("- name: Create successful fingerprint marker")
    assert release < evidence < success_marker


def test_artifact_contains_evidence_and_recovery_checkpoint() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "origin-evidence-adjudication.json" in text
    assert "origin-evidence-adjudication-checkpoint.json" in text
    assert "LLM output: `review signal only; never selection truth or mutation authority`" in text


def test_private_caller_requires_explicit_campaign_activation() -> None:
    text = CALLER.read_text(encoding="utf-8")

    assert "campaign_mode: benchmark" in text
    assert "benchmark_models: gpt-5.4-mini,gpt-5.6-terra,gpt-5.5" in text
    assert "benchmark_max_requests: 18" in text
    assert "benchmark_max_estimated_cost_usd: 0.50" in text
    assert "openai_api_key: ${{ secrets.OPENAI_API_KEY }}" in text


def test_success_and_checkpoint_caches_are_runtime_contract_bound() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Derive runtime contract cache key" in text
    assert "steps.runtime-contract.outputs.sha256" in text
    assert "RUNTIME_INPUTS_JSON: ${{ toJSON(inputs) }}" in text
