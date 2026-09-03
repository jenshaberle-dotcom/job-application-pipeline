from datetime import date
import hashlib
import json

from src.search_intelligence.product_v1_application_context import (
    ApplicationSourceDocumentSnapshot,
    ApplicationTargetSnapshot,
    CandidateFactSnapshot,
    build_product_v1_application_context,
)
from src.search_intelligence.product_v1_application_drafter_quality import (
    allowed_job_evidence,
    request_quality_application_draft,
)


def _context():
    detail = (
        "Our data platform team builds reliable production machine learning systems with Python, "
        "model monitoring and observability. You will design data pipelines, improve data quality, "
        "and work with engineering teams on scalable services for internal customers."
    )
    target = ApplicationTargetSnapshot(
        silver_job_id=434,
        product_rank=1,
        title="Machine Learning Engineer (m/f/d)",
        company_name="Example Energy",
        source_url="https://example.com/jobs/ml-engineer",
        canonical_source_type="employer_origin",
        product_readiness_status="rankable",
        origin_validation_status="validated",
        activity_status="active",
        hard_filter_status="passed",
        detail_text=detail,
        employer_origin_authorized=True,
    )
    cv_content = "PRIVATE CV STYLE REFERENCE EXPLICITLY APPROVED FOR GENERATION"
    letter_content = "PRIVATE LETTER STYLE REFERENCE EXPLICITLY APPROVED FOR GENERATION"
    documents = (
        ApplicationSourceDocumentSnapshot(
            document_type="base_cv",
            source_label="Current CV",
            source_reference="local://cv.pdf",
            content_sha256=hashlib.sha256(b"cv-bytes").hexdigest(),
            content=cv_content,
            status="approved",
            source_hash_verified=True,
        ),
        ApplicationSourceDocumentSnapshot(
            document_type="base_application_letter",
            source_label="Current letter",
            source_reference="local://letter.pdf",
            content_sha256=hashlib.sha256(b"letter-bytes").hexdigest(),
            content=letter_content,
            status="approved",
            source_hash_verified=True,
        ),
    )
    facts = (
        CandidateFactSnapshot(
            fact_key="employment.example.ml",
            category="employment",
            evidence_class="professional_employment",
            approval_status="approved",
            statement="Berufliche Erfahrung mit Machine Learning und Python in Engineering-Projekten.",
            capability_tags=("machine learning", "python"),
            limitations=(),
        ),
    )
    return build_product_v1_application_context(
        target=target,
        candidate_profile_status="approved",
        candidate_profile_sha256="a" * 64,
        candidate_facts=facts,
        source_documents=documents,
        as_of_date=date(2026, 9, 2),
    )


def test_allowed_job_evidence_is_exact_unique_and_bounded() -> None:
    context = _context()
    quotes = allowed_job_evidence(context)

    assert quotes
    assert len(quotes) <= 16
    for quote in quotes:
        assert context.target.detail_text.count(quote) == 1
        assert len(quote) <= 600


def test_quality_request_constrains_quotes_and_shares_only_approved_base_context() -> None:
    context = _context()
    quotes = allowed_job_evidence(context)
    captured: dict[str, object] = {}

    def transport(_url, _headers, payload, _timeout):
        captured.update(payload)
        draft = {
            "status": "draft_for_review",
            "fragments": [
                {
                    "kind": "cv_bullet",
                    "text": "Berufliche Erfahrung mit Machine Learning und Python in Engineering-Projekten.",
                    "candidate_fact_keys": ["employment.example.ml"],
                    "job_evidence": [],
                },
                {
                    "kind": "letter_opening",
                    "text": "Die Verbindung aus Machine Learning, Datenplattform und zuverlässigem Betrieb spricht mich besonders an.",
                    "candidate_fact_keys": [],
                    "job_evidence": [quotes[0]],
                },
                {
                    "kind": "letter_fit",
                    "text": "Meine berufliche Erfahrung mit Machine Learning und Python möchte ich gezielt in diese Aufgaben einbringen.",
                    "candidate_fact_keys": ["employment.example.ml"],
                    "job_evidence": [quotes[0]],
                },
                {
                    "kind": "letter_closing",
                    "text": "Über die Gelegenheit zu einem persönlichen Austausch freue ich mich.",
                    "candidate_fact_keys": [],
                    "job_evidence": [],
                },
            ],
            "rationale": "Source-grounded German review draft.",
        }
        return {
            "id": "resp-demo",
            "model": "demo-model",
            "output_text": json.dumps(draft, ensure_ascii=False),
            "usage": {"input_tokens": 10, "output_tokens": 10},
        }

    result = request_quality_application_draft(
        context=context,
        api_key="test-key",
        model="gpt-5.6-mini",
        transport=transport,
    )

    assert result.status == "completed"
    assert result.package is not None

    user_packet_text = captured["input"][1]["content"][0]["text"]
    user_packet = json.loads(user_packet_text)
    assert user_packet["allowed_job_evidence"] == list(quotes)
    assert [document["content"] for document in user_packet["base_documents"]] == [
        "PRIVATE CV STYLE REFERENCE EXPLICITLY APPROVED FOR GENERATION",
        "PRIVATE LETTER STYLE REFERENCE EXPLICITLY APPROVED FOR GENERATION",
    ]
    assert all(
        document["text_shared_with_provider"] is True
        for document in user_packet["base_documents"]
    )
    assert all(
        document["fact_authority_for_new_claims"] is False
        for document in user_packet["base_documents"]
    )
    assert user_packet["authority_constraints"]["draft_for_review_only"] is True
    assert user_packet["authority_constraints"]["submission_authority"] is False
    assert user_packet["authority_constraints"]["send_authority"] is False

    schema = captured["text"]["format"]["schema"]
    evidence_items = schema["properties"]["fragments"]["items"]["properties"]["job_evidence"]["items"]
    assert evidence_items["enum"] == list(quotes)
