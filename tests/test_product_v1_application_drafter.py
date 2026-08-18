from __future__ import annotations

from datetime import date
from hashlib import sha256
import json

from src.search_intelligence.llm_booster_policy import BoosterStage
from src.search_intelligence.product_v1_application_context import (
    ApplicationSourceDocumentSnapshot,
    ApplicationTargetSnapshot,
    CandidateFactSnapshot,
    build_product_v1_application_context,
)
from src.search_intelligence.product_v1_application_drafter import (
    ApplicationDraftObservation,
    execute_product_v1_application_drafter,
    request_product_v1_application_draft,
)


TODAY = date(2026, 8, 18)
DETAIL = (
    "Data Engineer role. We need Python and SQL for reliable data pipelines. "
    "The position is part of our analytics platform team."
)


def _document(document_type: str, content: str):
    return ApplicationSourceDocumentSnapshot(
        document_type=document_type,
        source_label=document_type,
        source_reference=f"local://{document_type}",
        content_sha256=sha256(content.encode("utf-8")).hexdigest(),
        content=content,
        status="approved",
    )


def _fact(
    fact_key: str,
    statement: str,
    tags: tuple[str, ...],
):
    return CandidateFactSnapshot(
        fact_key=fact_key,
        category="skill",
        evidence_class="professional_employment",
        approval_status="approved",
        statement=statement,
        capability_tags=tags,
        limitations=(),
    )


def _context(
    *,
    rank: int = 2,
    python_statement: str = "I have 5 years of professional Python experience.",
):
    target = ApplicationTargetSnapshot(
        silver_job_id=42,
        product_rank=rank,
        title="Data Engineer",
        company_name="Example GmbH",
        source_url="https://jobs.example.com/42",
        canonical_source_type="employer_origin",
        product_readiness_status="rankable",
        origin_validation_status="validated",
        activity_status="active",
        hard_filter_status="passed",
        detail_text=DETAIL,
    )
    return build_product_v1_application_context(
        target=target,
        candidate_profile_status="approved",
        candidate_profile_sha256="a" * 64,
        candidate_facts=(
            _fact("python", python_statement, ("Python",)),
            _fact("sql", "I use SQL professionally for data work.", ("SQL",)),
        ),
        source_documents=(
            _document("base_cv", "Old CV structure only."),
            _document("base_application_letter", "Old letter structure only."),
        ),
        as_of_date=TODAY,
    )


def _valid_fragments() -> list[dict[str, object]]:
    return [
        {
            "kind": "cv_bullet",
            "text": "5 years of professional Python experience.",
            "candidate_fact_keys": ["python"],
            "job_evidence": [],
        },
        {
            "kind": "letter_opening",
            "text": "I am applying for the Data Engineer role at Example GmbH.",
            "candidate_fact_keys": [],
            "job_evidence": ["Data Engineer role"],
        },
        {
            "kind": "letter_fit",
            "text": "My professional Python experience matches your Python requirement.",
            "candidate_fact_keys": ["python"],
            "job_evidence": ["Python"],
        },
        {
            "kind": "letter_closing",
            "text": "I would welcome the opportunity to discuss the role.",
            "candidate_fact_keys": [],
            "job_evidence": [],
        },
    ]


def _response(fragments: list[dict[str, object]]):
    return {
        "id": "resp_application_test",
        "model": "gpt-5.6-luna",
        "output_text": json.dumps(
            {
                "status": "draft_for_review",
                "fragments": fragments,
                "rationale": "bounded source-grounded draft",
            }
        ),
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }


def test_provider_accepts_source_grounded_draft_for_review_only() -> None:
    context = _context()
    payloads: list[dict[str, object]] = []

    def transport(_url, _headers, payload, _timeout):
        payloads.append(dict(payload))
        return _response(_valid_fragments())

    observation = request_product_v1_application_draft(
        context=context,
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )

    assert observation.status == "completed"
    assert observation.package is not None
    package = observation.package
    assert package.status == "draft_for_review"
    assert package.candidate_fact_keys_used == ("python",)
    assert package.draft_approval_authority is False
    assert package.application_authority is False
    assert package.submission_authority is False
    assert package.product_authority is False

    for fragment in package.fragments:
        for reference in fragment.job_evidence:
            assert DETAIL[reference.span_start : reference.span_end] == reference.evidence

    packet = json.loads(payloads[0]["input"][1]["content"][0]["text"])
    assert all("content" not in document for document in packet["base_documents"])
    assert all(document["fact_authority"] is False for document in packet["base_documents"])
    schema = payloads[0]["text"]["format"]["schema"]
    fragment_properties = schema["properties"]["fragments"]["items"]["properties"]
    assert set(fragment_properties) == {
        "kind",
        "text",
        "candidate_fact_keys",
        "job_evidence",
    }
    assert "approved" not in schema["properties"]
    assert "submit" not in schema["properties"]
    assert "send" not in schema["properties"]


def test_unknown_candidate_fact_key_fails_closed() -> None:
    context = _context()
    fragments = _valid_fragments()
    fragments[0] = {
        **fragments[0],
        "candidate_fact_keys": ["invented_fact"],
    }

    def transport(_url, _headers, _payload, _timeout):
        return _response(fragments)

    observation = request_product_v1_application_draft(
        context=context,
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )

    assert observation.status == "failed_closed"
    assert observation.package is None


def test_non_exact_vacancy_quote_fails_closed() -> None:
    context = _context()
    fragments = _valid_fragments()
    fragments[1] = {
        **fragments[1],
        "job_evidence": ["a role that is not in the vacancy"],
    }

    def transport(_url, _headers, _payload, _timeout):
        return _response(fragments)

    observation = request_product_v1_application_draft(
        context=context,
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )

    assert observation.status == "failed_closed"
    assert observation.package is None


def test_unsupported_numeric_claim_fails_closed() -> None:
    context = _context(python_statement="I use Python professionally.")
    fragments = _valid_fragments()
    fragments[0] = {
        **fragments[0],
        "text": "I bring 15 years of professional Python experience.",
    }

    def transport(_url, _headers, _payload, _timeout):
        return _response(fragments)

    observation = request_product_v1_application_draft(
        context=context,
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )

    assert observation.status == "failed_closed"
    assert observation.package is None


def test_non_ready_context_never_calls_provider() -> None:
    context = _context(rank=6)
    assert context.generation_ready is False

    def model(_stage):
        raise AssertionError("provider must not run for a blocked application context")

    execution = execute_product_v1_application_drafter(
        context=context,
        model=model,
    )

    assert execution.package is None
    assert execution.provider_requests == 0
    assert execution.llm_requests == 0
    assert execution.tavily_requests == 0
    assert execution.application_writes == 0
    assert execution.submission_writes == 0
    assert execution.send_actions == 0
    assert execution.application_authority is False
    assert all(not stage.attempted for stage in execution.stages[1:])


def test_invalid_luna_may_escalate_to_valid_terra_then_stops() -> None:
    context = _context()

    def valid_transport(_url, _headers, _payload, _timeout):
        return _response(_valid_fragments())

    valid = request_product_v1_application_draft(
        context=context,
        api_key="test-key",
        model="gpt-5.6-terra",
        transport=valid_transport,
    )
    assert valid.package is not None

    calls: list[BoosterStage] = []

    def model(stage):
        calls.append(stage)
        if stage == BoosterStage.LUNA_MEDIUM:
            return ApplicationDraftObservation(
                status="failed_closed",
                request_attempted=True,
                package=None,
                model="gpt-5.6-luna",
                estimated_cost_usd=0.001,
                rationale="malformed draft rejected",
            )
        return ApplicationDraftObservation(
            status="completed",
            request_attempted=True,
            package=valid.package,
            model="gpt-5.6-terra",
            estimated_cost_usd=0.001,
        )

    execution = execute_product_v1_application_drafter(
        context=context,
        model=model,
    )

    assert calls == [BoosterStage.LUNA_MEDIUM, BoosterStage.TERRA_MEDIUM]
    assert execution.package is valid.package
    assert execution.provider_requests == 2
    assert execution.llm_requests == 2
    luna = execution.stages[2]
    terra = execution.stages[3]
    assert luna.status == "unresolved"
    assert luna.reason_code == "draft_validation_failed_closed"
    assert terra.status == "draft_for_review"
    assert terra.reason_code == "source_grounded_draft_validated"
    assert all(not stage.attempted for stage in execution.stages[4:-1])
    assert execution.draft_approval_authority is False
    assert execution.application_authority is False
    assert execution.submission_authority is False
    assert execution.product_authority is False


def test_execution_rejects_model_application_authority_claim() -> None:
    context = _context()

    def model(_stage):
        return ApplicationDraftObservation(
            status="completed",
            request_attempted=True,
            package=None,
            model="gpt-5.6-luna",
            estimated_cost_usd=0.001,
            application_authority=True,
        )

    execution = execute_product_v1_application_drafter(
        context=context,
        model=model,
    )

    assert execution.package is None
    luna = execution.stages[2]
    assert luna.status == "failed_closed"
    assert luna.reason_code == "model_application_authority_claim_rejected"
    assert execution.provider_requests == 1
    assert execution.application_writes == 0
    assert execution.submission_writes == 0
    assert execution.send_actions == 0
    assert execution.application_authority is False
    assert execution.submission_authority is False
    assert execution.product_authority is False
