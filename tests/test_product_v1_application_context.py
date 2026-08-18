from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256

from src.search_intelligence.product_v1_application_context import (
    ApplicationSourceDocumentSnapshot,
    ApplicationTargetSnapshot,
    CandidateFactSnapshot,
    build_product_v1_application_context,
)


TODAY = date(2026, 8, 18)
DETAIL = (
    "We are looking for a Data Engineer with Python, SQL and test automation experience. "
    "The role builds reliable data pipelines."
)


def _target(**overrides):
    values = {
        "silver_job_id": 42,
        "product_rank": 2,
        "title": "Data Engineer",
        "company_name": "Example GmbH",
        "source_url": "https://jobs.example.com/42",
        "canonical_source_type": "employer_origin",
        "product_readiness_status": "rankable",
        "origin_validation_status": "validated",
        "activity_status": "active",
        "hard_filter_status": "passed",
        "detail_text": DETAIL,
    }
    values.update(overrides)
    return ApplicationTargetSnapshot(**values)


def _document(document_type: str, content: str):
    return ApplicationSourceDocumentSnapshot(
        document_type=document_type,
        source_label=f"approved {document_type}",
        source_reference=f"local://{document_type}",
        content_sha256=sha256(content.encode("utf-8")).hexdigest(),
        content=content,
        status="approved",
    )


def _fact(
    fact_key: str,
    statement: str,
    tags: tuple[str, ...],
    *,
    approval_status: str = "approved",
    valid_from: date | None = None,
    valid_until: date | None = None,
):
    return CandidateFactSnapshot(
        fact_key=fact_key,
        category="skill",
        evidence_class="professional_employment",
        approval_status=approval_status,
        statement=statement,
        capability_tags=tags,
        limitations=(),
        valid_from=valid_from,
        valid_until=valid_until,
    )


def test_ready_context_binds_top5_job_approved_docs_and_candidate_facts() -> None:
    context = build_product_v1_application_context(
        target=_target(),
        candidate_profile_status="approved",
        candidate_profile_sha256="a" * 64,
        candidate_facts=(
            _fact("python", "I use Python professionally.", ("Python",)),
            _fact("sql", "I use SQL for data work.", ("SQL",)),
            _fact("unrelated", "I facilitate workshops.", ("workshops",)),
        ),
        source_documents=(
            _document("base_cv", "CV structure and style"),
            _document("base_application_letter", "Letter structure and style"),
        ),
        as_of_date=TODAY,
    )

    assert context.generation_ready is True
    assert context.blocked_reasons == ()
    assert context.generation_context_authority is True
    assert context.application_authority is False
    assert context.submission_authority is False
    assert context.product_authority is False
    assert [fact.fact_key for fact in context.approved_candidate_facts] == [
        "python",
        "sql",
        "unrelated",
    ]
    assert [entry.fact_key for entry in context.claim_plan] == ["python", "sql"]

    for entry in context.claim_plan:
        for reference in entry.job_references:
            assert DETAIL[reference.span_start : reference.span_end] == reference.evidence

    manifest = context.source_manifest()
    assert manifest["target"]["product_rank"] == 2
    assert manifest["target"]["authority_source"] == "gold_product_v1_top_jobs"
    assert manifest["candidate_profile_sha256"] == "a" * 64
    assert all(document["fact_authority"] == "false" for document in manifest["documents"])


def test_non_top5_or_non_rankable_job_is_blocked() -> None:
    context = build_product_v1_application_context(
        target=_target(product_rank=6, product_readiness_status="hard_filter_decision_required"),
        candidate_profile_status="approved",
        candidate_profile_sha256="b" * 64,
        candidate_facts=(_fact("python", "I use Python professionally.", ("Python",)),),
        source_documents=(
            _document("base_cv", "CV"),
            _document("base_application_letter", "Letter"),
        ),
        as_of_date=TODAY,
    )

    assert context.generation_ready is False
    assert "authoritative_top5_rank_required" in context.blocked_reasons
    assert "job_not_rankable" in context.blocked_reasons
    assert context.generation_context_authority is False


def test_document_hash_mismatch_blocks_generation_and_never_grants_fact_authority() -> None:
    bad_cv = ApplicationSourceDocumentSnapshot(
        document_type="base_cv",
        source_label="CV",
        source_reference="local://cv",
        content_sha256="c" * 64,
        content="different content",
        status="approved",
    )
    context = build_product_v1_application_context(
        target=_target(),
        candidate_profile_status="approved",
        candidate_profile_sha256="d" * 64,
        candidate_facts=(_fact("python", "I use Python professionally.", ("Python",)),),
        source_documents=(bad_cv, _document("base_application_letter", "Letter")),
        as_of_date=TODAY,
    )

    assert context.generation_ready is False
    assert "base_cv_content_hash_mismatch" in context.blocked_reasons
    assert "missing_base_cv" in context.blocked_reasons
    assert context.candidate_fact_authority is False
    assert context.application_authority is False


def test_unapproved_future_and_expired_facts_are_not_claim_sources() -> None:
    context = build_product_v1_application_context(
        target=_target(),
        candidate_profile_status="approved",
        candidate_profile_sha256="e" * 64,
        candidate_facts=(
            _fact("approved", "I use Python professionally.", ("Python",)),
            _fact("proposed", "I am an expert in SQL.", ("SQL",), approval_status="proposed"),
            _fact(
                "future",
                "I will gain a certification.",
                ("SQL",),
                valid_from=TODAY + timedelta(days=1),
            ),
            _fact(
                "expired",
                "An old temporary claim.",
                ("SQL",),
                valid_until=TODAY - timedelta(days=1),
            ),
        ),
        source_documents=(
            _document("base_cv", "CV"),
            _document("base_application_letter", "Letter"),
        ),
        as_of_date=TODAY,
    )

    assert [fact.fact_key for fact in context.approved_candidate_facts] == ["approved"]
    assert [entry.fact_key for entry in context.claim_plan] == ["approved"]


def test_unapproved_candidate_profile_blocks_all_candidate_claims() -> None:
    context = build_product_v1_application_context(
        target=_target(),
        candidate_profile_status="draft",
        candidate_profile_sha256="f" * 64,
        candidate_facts=(_fact("python", "I use Python professionally.", ("Python",)),),
        source_documents=(
            _document("base_cv", "CV"),
            _document("base_application_letter", "Letter"),
        ),
        as_of_date=TODAY,
    )

    assert context.generation_ready is False
    assert context.approved_candidate_facts == ()
    assert context.claim_plan == ()
    assert "candidate_fact_profile_not_approved" in context.blocked_reasons
    assert "approved_candidate_facts_required" in context.blocked_reasons


def test_base_documents_are_style_sources_not_candidate_claim_sources() -> None:
    old_unsupported_claim = "I have 15 years of Kubernetes experience."
    context = build_product_v1_application_context(
        target=_target(),
        candidate_profile_status="approved",
        candidate_profile_sha256="1" * 64,
        candidate_facts=(_fact("python", "I use Python professionally.", ("Python",)),),
        source_documents=(
            _document("base_cv", old_unsupported_claim),
            _document("base_application_letter", old_unsupported_claim),
        ),
        as_of_date=TODAY,
    )

    assert context.generation_ready is True
    assert all("Kubernetes" not in entry.statement for entry in context.claim_plan)
    assert all(document["fact_authority"] == "false" for document in context.source_manifest()["documents"])
    payload = context.canonical_payload()
    assert payload["draft_approval_authority"] is False
    assert payload["application_authority"] is False
    assert payload["submission_authority"] is False
