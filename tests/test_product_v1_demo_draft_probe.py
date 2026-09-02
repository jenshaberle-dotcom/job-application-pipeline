from __future__ import annotations

from datetime import date
from hashlib import sha256

from scripts.run_product_v1_demo_draft_probe import (
    evaluate_draft_context,
    run_draft_probe,
)
from src.search_intelligence.product_v1_application_context import (
    ApplicationSourceDocumentSnapshot,
    ApplicationTargetSnapshot,
    CandidateFactSnapshot,
    build_product_v1_application_context,
)
from src.search_intelligence.product_v1_application_workspace import ApplicationWorkspaceStop


DETAIL = "Data Engineer role. We need Python and SQL for reliable data pipelines."


def _document(kind: str) -> ApplicationSourceDocumentSnapshot:
    content = f"{kind} style source"
    return ApplicationSourceDocumentSnapshot(
        document_type=kind,
        source_label=kind,
        source_reference=f"local://{kind}",
        content_sha256=sha256(content.encode("utf-8")).hexdigest(),
        content=content,
        status="approved",
    )


def _context(*, silver_job_id: int = 42):
    return build_product_v1_application_context(
        target=ApplicationTargetSnapshot(
            silver_job_id=silver_job_id,
            product_rank=1,
            title="Data Engineer",
            company_name="Example GmbH",
            source_url=f"https://jobs.example.com/{silver_job_id}",
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


def test_ready_context_proves_final_review_draft_provider_free() -> None:
    report = evaluate_draft_context(
        silver_job_id=42,
        context=_context(),
        final_url="https://jobs.example.com/42",
    )

    assert report["state"] == "pass"
    assert report["draft_mode"] == "deterministic_evidence_first"
    assert all(report["checks"].values())
    assert report["package"]["status"] == "draft_for_review"
    assert report["package"]["draft_approval_authority"] is False
    assert report["package"]["application_authority"] is False
    assert report["package"]["submission_authority"] is False
    assert report["boundaries"]["provider_requests"] == 0
    assert report["boundaries"]["database_writes"] == 0
    assert report["boundaries"]["submission_writes"] == 0
    assert report["boundaries"]["send_actions"] == 0


def test_selected_job_mismatch_fails_closed() -> None:
    report = run_draft_probe(
        silver_job_id=42,
        loader=lambda _job_id: (
            _context(silver_job_id=99),
            "https://jobs.example.com/99",
            "Data Engineer",
        ),
    )

    assert report["state"] == "blocked"
    assert report["blocking_checks"] == ["draft_runtime"]
    assert "not exact-bound" in report["reason"]
    assert report["boundaries"]["provider_requests"] == 0


def test_workspace_runtime_failure_remains_zero_provider_zero_write() -> None:
    def loader(_job_id: int):
        raise ApplicationWorkspaceStop("approved base letter is missing")

    report = run_draft_probe(silver_job_id=42, loader=loader)

    assert report["state"] == "blocked"
    assert report["reason"] == "approved base letter is missing"
    assert report["boundaries"] == {
        "provider_requests": 0,
        "database_writes": 0,
        "application_writes": 0,
        "submission_writes": 0,
        "send_actions": 0,
    }
