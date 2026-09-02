from __future__ import annotations

from datetime import date
from hashlib import sha256
from types import SimpleNamespace

from scripts import product_v1_application_workspace_runtime as runtime
from src.search_intelligence.product_v1_application_context import (
    ApplicationSourceDocumentSnapshot,
    ApplicationTargetSnapshot,
    CandidateFactSnapshot,
    build_product_v1_application_context,
)


DETAIL = "Data Engineer role. We need Python and SQL for reliable data pipelines."


def _document(kind: str) -> ApplicationSourceDocumentSnapshot:
    content = f"{kind} style only"
    return ApplicationSourceDocumentSnapshot(
        document_type=kind,
        source_label=kind,
        source_reference=f"local://{kind}",
        content_sha256=sha256(content.encode()).hexdigest(),
        content=content,
        status="approved",
    )


def _context():
    return build_product_v1_application_context(
        target=ApplicationTargetSnapshot(
            silver_job_id=42,
            product_rank=1,
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
            CandidateFactSnapshot(
                fact_key="python",
                category="skill",
                evidence_class="professional_employment",
                approval_status="approved",
                statement="I use Python professionally.",
                capability_tags=("Python",),
                limitations=(),
            ),
        ),
        source_documents=(_document("base_cv"), _document("base_application_letter")),
        as_of_date=date(2026, 9, 2),
    )


def _load(_silver_job_id: int):
    return _context(), "https://jobs.example.com/42", "Data Engineer"


def test_missing_provider_key_uses_zero_request_evidence_first_fallback(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "load_application_workspace", _load)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    payload = runtime.generate_application_draft_payload(42)

    assert payload["status"] == "draft_for_review"
    assert payload["draft_mode"] == "deterministic_evidence_first"
    assert payload["fallback_reason"] == "provider_key_unavailable"
    assert payload["provider_requests"] == 0
    assert payload["database_writes"] == 0
    assert payload["application_writes"] == 0
    assert payload["submission_writes"] == 0
    assert payload["send_actions"] == 0
    assert payload["package"]["draft_approval_authority"] is False
    assert payload["package"]["application_authority"] is False
    assert payload["package"]["submission_authority"] is False


def test_unresolved_provider_campaign_falls_back_without_write_authority(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "load_application_workspace", _load)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        runtime,
        "openai_application_draft_model_callback",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        runtime,
        "execute_product_v1_application_drafter",
        lambda **_kwargs: SimpleNamespace(
            package=None,
            provider_requests=2,
            llm_requests=2,
            estimated_model_cost_usd=0.004,
            stages=(),
        ),
    )

    payload = runtime.generate_application_draft_payload(42)

    assert payload["status"] == "draft_for_review"
    assert payload["draft_mode"] == "deterministic_evidence_first"
    assert payload["fallback_reason"] == "provider_campaign_unresolved"
    assert payload["provider_requests"] == 2
    assert payload["llm_requests"] == 2
    assert payload["estimated_model_cost_usd"] == 0.004
    assert payload["database_writes"] == 0
    assert payload["submission_writes"] == 0
    assert payload["send_actions"] == 0
