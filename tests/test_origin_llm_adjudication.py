from typing import Mapping

from src.search_intelligence.origin_llm_adjudication import (
    adjudicate_with_openai,
    build_adjudication_packet,
    final_review_state,
)
from src.search_intelligence.origin_source_evidence import (
    ArtifactCandidate,
    assess_origin_evidence_candidate,
    decide_origin_evidence,
    page_evidence_from_html,
)


def _ambiguous_decision():
    candidate = ArtifactCandidate(
        url="https://jobs.msg.group/jobs/data-engineer-123",
        provider="tavily",
        title="MSG Solutions GmbH Jobs",
        prior_identity_score=0.9,
    )
    page = page_evidence_from_html(
        requested_url=candidate.url,
        final_url=candidate.url,
        status_code=200,
        body=(
            '<html lang="de"><title>MSG Solutions GmbH Jobs</title>'
            '<a href="/jobs/data-engineer-123">Data Engineer Hannover</a></html>'
        ),
    )
    assessment = assess_origin_evidence_candidate(
        candidate_id="C1",
        candidate=candidate,
        company_key="msg_systems_ag",
        company_name="msg systems ag",
        page=page,
        target_location="Hannover",
    )
    return decide_origin_evidence(
        company_key="msg_systems_ag",
        company_name="msg systems ag",
        assessments=[assessment],
    )


def test_packet_exposes_bounded_candidates_and_no_mutation_boundary() -> None:
    packet = build_adjudication_packet(_ambiguous_decision())

    assert packet["schema_version"] == "origin_llm_adjudication_packet.v1"
    assert [item["candidate_id"] for item in packet["candidates"]] == ["C1"]
    assert packet["boundary"]["no_new_url"] is True
    assert packet["boundary"]["no_mutation"] is True


def test_openai_request_uses_strict_schema_and_store_false() -> None:
    captured: dict[str, object] = {}

    def transport(
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        captured.update(
            {
                "url": url,
                "headers": dict(headers),
                "payload": dict(payload),
                "timeout": timeout_seconds,
            }
        )
        return {
            "id": "resp_test",
            "model": "test-model",
            "usage": {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140},
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": (
                                '{"decision":"manual_review_required",'
                                '"recommended_candidate_id":"C1",'
                                '"entity_relationship":"ambiguous",'
                                '"origin_assessment":"verified_job_listing",'
                                '"manual_review_required":true,'
                                '"evidence_references":["C1"],'
                                '"remaining_uncertainty":["legal entity relationship"],'
                                '"rationale":"The listing exists, but the entity differs."}'
                            ),
                        }
                    ]
                }
            ],
        }

    result = adjudicate_with_openai(
        _ambiguous_decision(),
        api_key="test-secret",
        model="test-model",
        transport=transport,
    )

    assert result.status == "completed"
    assert result.adjudication is not None
    assert captured["payload"]["store"] is False
    assert captured["payload"]["text"]["format"]["strict"] is True
    assert captured["headers"]["Authorization"] == "Bearer test-secret"
    assert final_review_state(_ambiguous_decision(), result) == "manual_review_required"


def test_invented_candidate_fails_closed() -> None:
    def transport(*_args):
        return {
            "output_text": (
                '{"decision":"prefer_alternative",'
                '"recommended_candidate_id":"C99",'
                '"entity_relationship":"brand_match",'
                '"origin_assessment":"verified_job_listing",'
                '"manual_review_required":false,'
                '"evidence_references":["C99"],'
                '"remaining_uncertainty":[],'
                '"rationale":"Invented."}'
            )
        }

    result = adjudicate_with_openai(
        _ambiguous_decision(),
        api_key="test-secret",
        model="test-model",
        transport=transport,
    )

    assert result.status == "failed_closed"
    assert result.adjudication is None
    assert result.request_attempted is True
