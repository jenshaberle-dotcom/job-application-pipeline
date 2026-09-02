from __future__ import annotations

from datetime import date
from hashlib import sha256

import pytest

from src.search_intelligence.product_v1_application_context import (
    ApplicationSourceDocumentSnapshot,
    ApplicationTargetSnapshot,
    CandidateFactSnapshot,
    build_product_v1_application_context,
)
from src.search_intelligence.product_v1_evidence_first_draft import (
    EvidenceFirstDraftStop,
    build_evidence_first_review_draft,
)


DETAIL = (
    "Data Engineer role. We need Python and SQL for reliable data pipelines. "
    "The position is part of our analytics platform team."
)


def _document(document_type: str, content: str) -> ApplicationSourceDocumentSnapshot:
    return ApplicationSourceDocumentSnapshot(
        document_type=document_type,
        source_label=document_type,
        source_reference=f"local://{document_type}",
        content_sha256=sha256(content.encode("utf-8")).hexdigest(),
        content=content,
        status="approved",
    )


def _fact(key: str, statement: str, tag: str) -> CandidateFactSnapshot:
    return CandidateFactSnapshot(
        fact_key=key,
        category="skill",
        evidence_class="professional_employment",
        approval_status="approved",
        statement=statement,
        capability_tags=(tag,),
        limitations=(),
    )


def _context(*, rank: int = 2):
    return build_product_v1_application_context(
        target=ApplicationTargetSnapshot(
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
        ),
        candidate_profile_status="approved",
        candidate_profile_sha256="a" * 64,
        candidate_facts=(
            _fact(
                "python",
                "I have 5 years of professional Python experience.",
                "Python",
            ),
            _fact(
                "sql",
                "I use SQL professionally for data work.",
                "SQL",
            ),
        ),
        source_documents=(
            _document("base_cv", "CV style source only."),
            _document("base_application_letter", "Letter style source only."),
        ),
        as_of_date=date(2026, 9, 2),
    )


def test_evidence_first_draft_is_review_only_and_exact_grounded() -> None:
    context = _context()
    package = build_evidence_first_review_draft(context)

    assert package.status == "draft_for_review"
    assert package.candidate_fact_keys_used == ("python", "sql")
    assert package.draft_approval_authority is False
    assert package.application_authority is False
    assert package.submission_authority is False
    assert package.product_authority is False
    assert "Deterministic evidence-first fallback" in package.rationale

    kinds = [fragment.kind for fragment in package.fragments]
    assert kinds == [
        "cv_summary",
        "cv_bullet",
        "letter_opening",
        "letter_fit",
        "letter_closing",
    ]
    assert package.fragments[0].text == context.claim_plan[0].statement
    assert package.fragments[1].text == context.claim_plan[1].statement

    for fragment in package.fragments:
        for reference in fragment.job_evidence:
            assert DETAIL[reference.span_start : reference.span_end] == reference.evidence


def test_evidence_first_draft_is_deterministic_for_same_context() -> None:
    context = _context()
    first = build_evidence_first_review_draft(context).canonical_payload()
    second = build_evidence_first_review_draft(context).canonical_payload()
    assert first == second


def test_evidence_first_draft_blocks_non_ready_context() -> None:
    context = _context(rank=6)
    assert context.generation_ready is False
    with pytest.raises(EvidenceFirstDraftStop, match="context is not ready"):
        build_evidence_first_review_draft(context)


def test_evidence_first_draft_never_uses_base_document_text_as_fact_authority() -> None:
    context = _context()
    package = build_evidence_first_review_draft(context)
    serialized = str(package.canonical_payload())

    assert "CV style source only" not in serialized
    assert "Letter style source only" not in serialized
    assert "5 years of professional Python experience" in serialized
    assert "I use SQL professionally" in serialized
