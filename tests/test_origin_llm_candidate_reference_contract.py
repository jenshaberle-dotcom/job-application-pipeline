from src.search_intelligence.origin_llm_model_campaign import build_request_payload
from src.search_intelligence.origin_source_evidence import (
    OriginEvidenceAssessment,
    OriginEvidenceDecision,
)


def _assessment(candidate_id: str, url: str) -> OriginEvidenceAssessment:
    return OriginEvidenceAssessment(
        candidate_id=candidate_id,
        url=url,
        final_url=url,
        provider="tavily",
        source_grade="company_job_listing",
        entity_fidelity="exact_legal_entity",
        job_inventory_state="job_bearing_proven",
        page_type="job_listing",
        ats_family=None,
        http_status=200,
        reachable=True,
        locale="de",
        observed_job_count=3,
        target_signal_job_count=1,
        sample_job_urls=(f"{url}/job/1",),
        identity_score=0.9,
        source_grade_score=0.94,
        entity_fidelity_score=1.0,
        job_bearing_score=1.0,
        locale_preference_score=1.0,
        target_relevance_score=0.7,
        evidence_completeness=0.9,
        ranking_score=0.9,
        reasons=("fixture",),
        failure_class=None,
    )


def _decision() -> OriginEvidenceDecision:
    assessments = (
        _assessment("C1", "https://jobs.example.de/careers"),
        _assessment("C2", "https://jobs.example.de/stellenangebote"),
    )
    return OriginEvidenceDecision(
        company_key="example_ag",
        company_name="Example AG",
        deterministic_decision="origin_url_candidate_selected",
        selected_candidate_id="C1",
        selected_url=assessments[0].final_url,
        confidence_score=0.72,
        confidence_band="medium",
        selection_margin=0.18,
        manual_review_required=False,
        adjudication_reasons=(),
        assessments=assessments,
    )


def test_model_campaign_schema_allows_only_packet_candidate_ids() -> None:
    payload, _packet_hash, _contract_hash = build_request_payload(
        _decision(),
        model="gpt-5.4-mini",
        reasoning_effort="low",
        max_output_tokens=1200,
    )

    schema = payload["text"]["format"]["schema"]
    properties = schema["properties"]
    assert properties["recommended_candidate_id"]["enum"] == ["C1", "C2", None]
    assert properties["evidence_references"]["items"]["enum"] == ["C1", "C2"]


def test_model_campaign_prompt_forbids_prose_evidence_references() -> None:
    payload, _packet_hash, _contract_hash = build_request_payload(
        _decision(),
        model="gpt-5.4-mini",
    )

    instructions = payload["input"][0]["content"][0]["text"]
    assert "Use exact candidate_id values only" in instructions
    assert "evidence_references must never contain prose" in instructions
