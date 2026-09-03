from types import SimpleNamespace

from src.search_intelligence.product_v1_application_drafter_quality import (
    MAX_BASE_DOCUMENT_CHARS,
    QUALITY_SYSTEM_INSTRUCTIONS,
    _quality_packet,
)


class ContextStub:
    def __init__(self) -> None:
        self.target = SimpleNamespace(
            title="Data Engineer",
            company_name="Muster GmbH",
            source_url="https://example.com/job/1",
            detail_text="Python und SQL für zuverlässige Datenpipelines.",
        )
        self.claim_plan = (
            SimpleNamespace(
                fact_key="project.pipeline",
                statement="Entwicklung einer Datenpipeline mit Python und PostgreSQL.",
                limitations=(),
                matched_capability_tags=("python", "sql"),
            ),
        )
        self.source_documents = (
            SimpleNamespace(
                document_type="base_cv",
                source_label="Approved CV",
                content_sha256="a" * 64,
                content="CV STYLE CONTENT",
            ),
            SimpleNamespace(
                document_type="base_application_letter",
                source_label="Approved letter",
                content_sha256="b" * 64,
                content="LETTER STYLE CONTENT",
            ),
        )

    def source_manifest(self) -> dict[str, object]:
        return {"manifest": "stable"}


def test_quality_packet_shares_only_explicit_approved_base_document_context() -> None:
    packet = _quality_packet(ContextStub(), ("exact vacancy evidence",))

    base_documents = packet["base_documents"]
    assert isinstance(base_documents, list)
    assert [document["content"] for document in base_documents] == [
        "CV STYLE CONTENT",
        "LETTER STYLE CONTENT",
    ]
    assert all(document["text_shared_with_provider"] is True for document in base_documents)
    assert all(document["fact_authority_for_new_claims"] is False for document in base_documents)
    assert packet["authority_constraints"]["base_document_text_shared_with_provider"] is True
    assert packet["authority_constraints"]["base_document_fact_authority_for_new_claims"] is False


def test_base_document_provider_context_is_bounded_and_prompt_forbids_stale_letter_target() -> None:
    context = ContextStub()
    context.source_documents = (
        SimpleNamespace(
            document_type="base_cv",
            source_label="Approved CV",
            content_sha256="a" * 64,
            content="x" * (MAX_BASE_DOCUMENT_CHARS + 500),
        ),
    )

    packet = _quality_packet(context, ("exact vacancy evidence",))
    assert len(packet["base_documents"][0]["content"]) == MAX_BASE_DOCUMENT_CHARS
    assert "Never carry forward an old employer" in QUALITY_SYSTEM_INSTRUCTIONS
    assert "experienced German application writer" in QUALITY_SYSTEM_INSTRUCTIONS
