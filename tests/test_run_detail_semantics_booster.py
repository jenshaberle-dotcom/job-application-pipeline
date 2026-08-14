from __future__ import annotations

import json

import pytest

import scripts.run_detail_semantics_booster as runner
from src.search_intelligence.detail_semantics_booster_execution import (
    DetailSemanticsHypothesisObservation,
)
from src.search_intelligence.detail_semantics_gap import SemanticEvidenceReference

DETAIL_URL = "https://jobs.example.com/jobs/42-data-engineer"
SUPPORTED_HTML = """
<html>
  <head><title>Data Engineer Hannover</title></head>
  <body>
    <h1>Data Engineer</h1>
    <p>Standort Hannover</p>
    <p>Python und SQL sind Teil des Stacks.</p>
  </body>
</html>
"""


def parse_args(*extra: str):  # type: ignore[no-untyped-def]
    return runner.build_parser().parse_args(
        [
            "--company-name",
            "Example GmbH",
            "--detail-url",
            DETAIL_URL,
            *extra,
        ]
    )


def test_deterministic_requested_fields_skip_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner,
        "fetch_url",
        lambda url: (SUPPORTED_HTML, DETAIL_URL, 200),
    )
    monkeypatch.setattr(
        runner,
        "request_detail_semantics_hypotheses",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("provider must not run")),
    )

    payload = runner.run(
        parse_args("--semantic-field", "role", "--semantic-field", "location")
    )

    assert payload["outcome"] == "DETERMINISTIC_SEMANTICS_RESOLVED"
    assert payload["provider_requests"] == 0
    assert payload["llm_requests"] == 0
    assert payload["database_writes"] == 0
    assert payload["gate_writes"] == 0
    assert payload["product_writes"] == 0
    assert payload["semantic_authority"] is False
    assert payload["product_authority"] is False
    assert payload["detail"]["raw_html_persisted"] is False
    assert "html" not in payload["detail"]


def test_missing_requested_field_runs_luna_and_span_revalidation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = """
    <html><head><title>Data Engineer Hannover</title></head>
    <body><p>Experienced Data Engineer für Hannover.</p><p>Python.</p></body></html>
    """
    monkeypatch.setattr(runner, "fetch_url", lambda url: (html, DETAIL_URL, 200))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls: list[str] = []

    def provider(**kwargs):  # type: ignore[no-untyped-def]
        calls.append(str(kwargs["model"]))
        detail_text = str(kwargs["detail_text"])
        evidence = "Experienced"
        start = detail_text.index(evidence)
        return DetailSemanticsHypothesisObservation(
            status="completed",
            request_attempted=True,
            semantic_fields={"seniority": "Experienced"},
            evidence_references=(
                SemanticEvidenceReference(
                    field="seniority",
                    source_url=DETAIL_URL,
                    evidence=evidence,
                    value="Experienced",
                    span_start=start,
                    span_end=start + len(evidence),
                ),
            ),
            model=str(kwargs["model"]),
            response_id="resp_test",
            estimated_cost_usd=0.001,
            rationale="test",
            product_authority=False,
        )

    monkeypatch.setattr(runner, "request_detail_semantics_hypotheses", provider)

    payload = runner.run(parse_args("--semantic-field", "seniority"))

    assert calls == ["gpt-5.6-luna"]
    assert payload["outcome"] == "SEMANTIC_BOOSTER_RESOLVED"
    assert payload["provider_requests"] == 1
    assert payload["llm_requests"] == 1
    assert payload["execution"]["semantic_fields"] == {"seniority": "Experienced"}
    assert payload["execution"]["resolved"] is True
    assert payload["product_authority"] is False


def test_product_support_does_not_resolve_missing_semantics_when_llm_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner,
        "fetch_url",
        lambda url: (SUPPORTED_HTML, DETAIL_URL, 200),
    )

    payload = runner.run(
        parse_args("--semantic-field", "seniority", "--disable-llm")
    )

    assert payload["profile_contract_satisfied"] is True
    assert payload["geography_contract_satisfied"] is True
    assert payload["detail_supported"] is True
    assert payload["outcome"] == "RESIDUAL_SEMANTICS_UNRESOLVED"
    assert payload["provider_requests"] == 0
    assert payload["llm_requests"] == 0


def test_unsupported_detail_truth_prevents_model_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = "<html><head><title>Data Engineer Berlin</title></head><body>Python.</body></html>"
    monkeypatch.setattr(runner, "fetch_url", lambda url: (html, DETAIL_URL, 200))
    monkeypatch.setattr(
        runner,
        "request_detail_semantics_hypotheses",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("provider must not run")),
    )

    payload = runner.run(parse_args("--semantic-field", "seniority"))

    assert payload["detail_supported"] is False
    assert payload["outcome"] == "SEMANTIC_BOOSTER_NOT_ELIGIBLE"
    assert payload["provider_requests"] == 0
    assert payload["llm_requests"] == 0


def test_cross_domain_redirect_fails_before_semantic_or_provider_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner,
        "fetch_url",
        lambda url: (SUPPORTED_HTML, "https://evil.example/jobs/42", 200),
    )

    payload = runner.run(parse_args("--semantic-field", "role"))

    assert payload["result"] == "DETAIL_SEMANTICS_FETCH_FAILED"
    assert "outside the original base domain" in payload["failure_reason"]
    assert payload["provider_requests"] == 0
    assert payload["product_authority"] is False


def test_grounding_rejects_provider_reference_with_changed_detail_text() -> None:
    observation_fields = {"role": "Data Engineer"}
    reference = SemanticEvidenceReference(
        field="role",
        source_url=DETAIL_URL,
        evidence="Data Engineer",
        value="Data Engineer",
        span_start=0,
        span_end=len("Data Engineer"),
    )

    assert runner._references_ground_fields(
        detail_url=DETAIL_URL,
        detail_text="Data Engineer Hannover",
        semantic_fields=observation_fields,
        references=(reference,),
    )
    assert not runner._references_ground_fields(
        detail_url=DETAIL_URL,
        detail_text="Senior Engineer Hannover",
        semantic_fields=observation_fields,
        references=(reference,),
    )


def test_output_is_json_serializable_and_contains_no_raw_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner,
        "fetch_url",
        lambda url: (SUPPORTED_HTML, DETAIL_URL, 200),
    )

    payload = runner.run(parse_args("--semantic-field", "role"))
    rendered = json.dumps(payload, ensure_ascii=False)

    assert "<html>" not in rendered
    assert '"raw_html_persisted": false' in rendered
