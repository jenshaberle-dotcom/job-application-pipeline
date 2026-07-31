from pathlib import Path


def test_smoke_contract_is_three_calls_without_cost_stop() -> None:
    text = Path(
        "docs/reference/search-intelligence/origin_llm_smoke_contract.v1.md"
    ).read_text(encoding="utf-8")

    assert "benchmark cases: `1`" in text
    assert "exact maximum provider requests: `3`" in text
    assert "no application-level retry" in text
    assert "never used as a stop gate" in text
    assert "review_output_only_not_pipeline_input" in text
