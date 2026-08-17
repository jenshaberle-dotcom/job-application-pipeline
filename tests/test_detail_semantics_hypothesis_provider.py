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


def hypothesis(observed_value: str, evidence: str, *, field: str) -> dict[str, object]:
    return {"field": field, "observed_value": observed_value, "evidence": evidence}


def test_exact_quotes_receive_deterministic_same_detail_offsets_and_normalization() -> None:
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
                    hypothesis("Data Engineer", "Senior Data Engineer", field="role"),
                    hypothesis("Senior", "Senior Data Engineer", field="seniority"),
                    hypothesis("Hannover", "in Hannover", field="location"),
                    hypothesis("Hybrid", "Hybrid work", field="remote"),
                ]
            )
        ),
    )

    assert observation.status == "completed"
    assert observation.request_attempted is True
    assert observation.semantic_fields == {
        "role": "Data Engineer",
        "seniority": "senior",
        "location": "Hannover",
        "remote": "hybrid",
    }
    assert [item.value for item in observation.evidence_references] == [
        "Data Engineer",
        "Senior",
        "Hannover",
        "Hybrid",
    ]
    assert len(observation.evidence_references) == 4
    assert all(item.source_url == DETAIL_URL for item in observation.evidence_references)
    assert all(
        item.span_start is not None
        and item.span_end is not None
        and DETAIL_TEXT[item.span_start : item.span_end] == item.evidence
        for item in observation.evidence_references
    )
    assert observation.product_authority is False


def test_provider_contract_asks_for_observed_source_value_not_model_canonicalization() -> None:
    captured: list[dict[str, object]] = []

    def transport(url, headers, payload, timeout_seconds):  # type: ignore[no-untyped-def]
        captured.append(payload)
        return response_for([])

    observation = request_detail_semantics_hypotheses(
        company_name="Example GmbH",
        detail_url=DETAIL_URL,
        detail_text=DETAIL_TEXT,
        requested_semantic_fields=("role",),
        current_semantic_fields={},
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )

    assert observation.status == "completed"
    schema = captured[0]["text"]["format"]["schema"]  # type: ignore[index]
    item_schema = schema["properties"]["hypotheses"]["items"]  # type: ignore[index]
    assert item_schema["required"] == ["field", "observed_value", "evidence"]
    assert "value" not in item_schema["properties"]
    assert "span_start" not in item_schema["properties"]
    assert "span_end" not in item_schema["properties"]

    packet = json.loads(captured[0]["input"][1]["content"][0]["text"])  # type: ignore[index]
    assert packet["authority_constraints"]["exact_evidence_quote_required"] is True
    assert packet["authority_constraints"]["observed_source_value_required"] is True
    assert packet["authority_constraints"]["deterministic_field_normalization_required"] is True
    assert packet["authority_constraints"]["deterministic_unique_span_required"] is True


def test_multiple_skill_hypotheses_are_normalized_and_raw_values_are_retained() -> None:
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
                    hypothesis("Python", "Python und SQL", field="skills"),
                    hypothesis("SQL", "Python und SQL", field="skills"),
                ]
            )
        ),
    )

    assert observation.status == "completed"
    assert observation.semantic_fields == {"skills": ("python", "sql")}
    assert [item.value for item in observation.evidence_references] == ["Python", "SQL"]
    assert len(observation.evidence_references) == 2
    assert observation.product_authority is False


def test_quote_missing_from_bounded_detail_fails_closed() -> None:
    observation = request_detail_semantics_hypotheses(
        company_name="Example GmbH",
        detail_url=DETAIL_URL,
        detail_text=DETAIL_TEXT,
        requested_semantic_fields=("role",),
        current_semantic_fields={},
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport_returning(
            response_for([hypothesis("Data Engineer", "Data Engineer Berlin", field="role")])
        ),
    )

    assert observation.status == "failed_closed"
    assert observation.semantic_fields == {}
    assert observation.evidence_references == ()
    assert "does not occur in bounded detail text" in observation.rationale
    assert observation.product_authority is False


def test_repeated_exact_quote_is_ambiguous_and_fails_closed() -> None:
    repeated_text = "Python ist erforderlich. Python ist ein Plus."
    observation = request_detail_semantics_hypotheses(
        company_name="Example GmbH",
        detail_url=DETAIL_URL,
        detail_text=repeated_text,
        requested_semantic_fields=("skills",),
        current_semantic_fields={},
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport_returning(
            response_for([hypothesis("Python", "Python", field="skills")])
        ),
    )

    assert observation.status == "failed_closed"
    assert "ambiguous in bounded detail text" in observation.rationale


def test_model_canonicalization_without_observed_source_value_fails_closed() -> None:
    detail_text = "Home Office ist möglich."
    observation = request_detail_semantics_hypotheses(
        company_name="Example GmbH",
        detail_url=DETAIL_URL,
        detail_text=detail_text,
        requested_semantic_fields=("remote",),
        current_semantic_fields={},
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport_returning(
            response_for([hypothesis("remote", "Home Office", field="remote")])
        ),
    )

    assert observation.status == "failed_closed"
    assert "observed source value must occur verbatim" in observation.rationale


def test_home_office_source_phrase_is_grounded_before_normalization() -> None:
    detail_text = "Home Office ist möglich."
    observation = request_detail_semantics_hypotheses(
        company_name="Example GmbH",
        detail_url=DETAIL_URL,
        detail_text=detail_text,
        requested_semantic_fields=("remote",),
        current_semantic_fields={},
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport_returning(
            response_for([hypothesis("Home Office", "Home Office", field="remote")])
        ),
    )

    assert observation.status == "completed"
    assert observation.semantic_fields == {"remote": "home office"}
    assert observation.evidence_references[0].value == "Home Office"
    assert observation.evidence_references[0].evidence == "Home Office"


def test_years_of_experience_are_not_normalized_into_seniority() -> None:
    detail_text = "5 years experience with data platforms."
    observation = request_detail_semantics_hypotheses(
        company_name="Example GmbH",
        detail_url=DETAIL_URL,
        detail_text=detail_text,
        requested_semantic_fields=("seniority",),
        current_semantic_fields={},
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport_returning(
            response_for(
                [hypothesis("5 years experience", "5 years experience", field="seniority")]
            )
        ),
    )

    assert observation.status == "failed_closed"
    assert "must not be normalized into seniority" in observation.rationale


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
            response_for([hypothesis("Hannover", "in Hannover", field="location")])
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
                    hypothesis("Data Engineer", "Senior Data Engineer", field="role"),
                    hypothesis("Senior Data Engineer", "Senior Data Engineer", field="role"),
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
