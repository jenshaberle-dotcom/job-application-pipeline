from __future__ import annotations

import json
from typing import Mapping

import pytest

from src.search_intelligence.detail_semantics_hypothesis_provider import (
    MAX_DETAIL_TEXT_CHARS,
    request_detail_semantics_hypotheses,
)

DETAIL_URL = "https://jobs.example.com/jobs/42-data-engineer"
DETAIL_TEXT = "Senior Data Engineer in Hannover. Python und SQL. Hybrid work möglich."


def response_for(hypotheses: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": "resp_semantics_1",
        "model": "gpt-5.6-luna",
        "output_text": json.dumps(
            {"hypotheses": hypotheses, "rationale": "bounded evidence only"}
        ),
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }


def transport_returning(
    response: Mapping[str, object],
):  # type: ignore[no-untyped-def]
    def transport(url, headers, payload, timeout_seconds):  # type: ignore[no-untyped-def]
        assert headers["Authorization"] == "Bearer test-key"
        assert payload["store"] is False
        return response

    return transport


def span(value: str, evidence: str, *, field: str) -> dict[str, object]:
    start = DETAIL_TEXT.index(evidence)
    return {
        "field": field,
        "value": value,
        "evidence": evidence,
        "span_start": start,
        "span_end": start + len(evidence),
    }


def test_exact_spans_become_same_detail_evidence_references() -> None:
    observation = request_detail_semantics_hypotheses(
        company_name="Example GmbH",
        detail_url=DETAIL_URL,
        detail_text=DETAIL_TEXT,
        requested_semantic_fields=("role", "seniority", "location", "remote"),
        current_semantic_fields={},
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport_returning(
            response_for(
                [
                    span("Data Engineer", "Senior Data Engineer", field="role"),
                    span("Senior", "Senior Data Engineer", field="seniority"),
                    span("Hannover", "in Hannover", field="location"),
                    span("Hybrid", "Hybrid work", field="remote"),
                ]
            )
        ),
    )

    assert observation.status == "completed"
    assert observation.request_attempted is True
    assert observation.semantic_fields == {
        "role": "Data Engineer",
        "seniority": "Senior",
        "location": "Hannover",
        "remote": "Hybrid",
    }
    assert len(observation.evidence_references) == 4
    assert all(item.source_url == DETAIL_URL for item in observation.evidence_references)
    assert all(
        DETAIL_TEXT[item.span_start : item.span_end] == item.evidence
        for item in observation.evidence_references
        if item.span_start is not None and item.span_end is not None
    )
    assert observation.product_authority is False


def test_multiple_skill_hypotheses_are_aggregated_without_authority() -> None:
    observation = request_detail_semantics_hypotheses(
        company_name="Example GmbH",
        detail_url=DETAIL_URL,
        detail_text=DETAIL_TEXT,
        requested_semantic_fields=("skills",),
        current_semantic_fields={},
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport_returning(
            response_for(
                [
                    span("Python", "Python und SQL", field="skills"),
                    span("SQL", "Python und SQL", field="skills"),
                ]
            )
        ),
    )

    assert observation.status == "completed"
    assert observation.semantic_fields == {"skills": ("Python", "SQL")}
    assert len(observation.evidence_references) == 2
    assert observation.product_authority is False


def test_mismatched_span_fails_closed_before_executor() -> None:
    bad = span("Data Engineer", "Senior Data Engineer", field="role")
    bad["span_end"] = int(bad["span_end"]) - 1

    observation = request_detail_semantics_hypotheses(
        company_name="Example GmbH",
        detail_url=DETAIL_URL,
        detail_text=DETAIL_TEXT,
        requested_semantic_fields=("role",),
        current_semantic_fields={},
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport_returning(response_for([bad])),
    )

    assert observation.status == "failed_closed"
    assert observation.semantic_fields == {}
    assert observation.evidence_references == ()
    assert "span does not match" in observation.rationale
    assert observation.product_authority is False


def test_value_must_occur_verbatim_inside_evidence() -> None:
    bad = span("Principal", "Senior Data Engineer", field="seniority")

    observation = request_detail_semantics_hypotheses(
        company_name="Example GmbH",
        detail_url=DETAIL_URL,
        detail_text=DETAIL_TEXT,
        requested_semantic_fields=("seniority",),
        current_semantic_fields={},
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport_returning(response_for([bad])),
    )

    assert observation.status == "failed_closed"
    assert "value must occur verbatim" in observation.rationale


def test_unrequested_field_fails_closed() -> None:
    observation = request_detail_semantics_hypotheses(
        company_name="Example GmbH",
        detail_url=DETAIL_URL,
        detail_text=DETAIL_TEXT,
        requested_semantic_fields=("role",),
        current_semantic_fields={},
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport_returning(
            response_for([span("Hannover", "in Hannover", field="location")])
        ),
    )

    assert observation.status == "failed_closed"
    assert "unrequested semantic field" in observation.rationale


def test_duplicate_scalar_field_fails_closed() -> None:
    observation = request_detail_semantics_hypotheses(
        company_name="Example GmbH",
        detail_url=DETAIL_URL,
        detail_text=DETAIL_TEXT,
        requested_semantic_fields=("role",),
        current_semantic_fields={},
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport_returning(
            response_for(
                [
                    span("Data Engineer", "Senior Data Engineer", field="role"),
                    span("Senior Data Engineer", "Senior Data Engineer", field="role"),
                ]
            )
        ),
    )

    assert observation.status == "failed_closed"
    assert "duplicate scalar semantic field" in observation.rationale


def test_provider_packet_truncates_detail_text_to_hard_bound() -> None:
    captured_text: list[str] = []

    def transport(url, headers, payload, timeout_seconds):  # type: ignore[no-untyped-def]
        user_packet = json.loads(payload["input"][1]["content"][0]["text"])
        captured_text.append(user_packet["detail_text"])
        return response_for([])

    observation = request_detail_semantics_hypotheses(
        company_name="Example GmbH",
        detail_url=DETAIL_URL,
        detail_text="x" * (MAX_DETAIL_TEXT_CHARS + 100),
        requested_semantic_fields=("role",),
        current_semantic_fields={},
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )

    assert observation.status == "completed"
    assert len(captured_text) == 1
    assert len(captured_text[0]) == MAX_DETAIL_TEXT_CHARS


def test_invalid_requested_scope_is_rejected_before_network() -> None:
    with pytest.raises(ValueError, match="unsupported requested semantic field"):
        request_detail_semantics_hypotheses(
            company_name="Example GmbH",
            detail_url=DETAIL_URL,
            detail_text=DETAIL_TEXT,
            requested_semantic_fields=("salary",),
            current_semantic_fields={},
            api_key="test-key",
            model="gpt-5.6-luna",
            transport=lambda *args: response_for([]),
        )
