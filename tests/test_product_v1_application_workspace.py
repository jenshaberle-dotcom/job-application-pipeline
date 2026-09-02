from __future__ import annotations

from datetime import date
from hashlib import sha256
from pathlib import Path

import pytest

from src.search_intelligence.product_v1_application_workspace import (
    ApplicationWorkspaceStop,
    build_application_workspace_context,
    local_document_loader,
)


def _job() -> dict[str, object]:
    return {
        "silver_job_id": 42,
        "product_rank": 1,
        "title": "Machine Learning Engineer",
        "company_name": "Example GmbH",
        "source_url": "https://jobs.example.test/job/42",
        "canonical_source_type": "employer_origin",
        "product_readiness_status": "rankable",
        "origin_validation_status": "validated",
        "activity_status": "active",
        "hard_filter_status": "passed",
    }


def _fact() -> dict[str, object]:
    return {
        "fact_key": "python",
        "category": "skill",
        "evidence_class": "professional_employment",
        "approval_status": "approved",
        "statement": "I use Python professionally for data and automation work.",
        "capability_tags": ["Python"],
        "limitations": [],
        "valid_from": None,
        "valid_until": None,
    }


def _documents(root: Path) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for document_type, content in (
        ("base_cv", "Canonical CV structure"),
        ("base_application_letter", "Canonical application letter structure"),
    ):
        path = root / f"{document_type}.txt"
        path.write_text(content, encoding="utf-8")
        result.append(
            {
                "document_type": document_type,
                "source_label": document_type,
                "source_reference": f"local://{path.name}",
                "content_sha256": sha256(content.encode("utf-8")).hexdigest(),
                "status": "approved",
            }
        )
    return result


def test_ready_workspace_binds_top5_facts_documents_and_job_evidence(
    tmp_path: Path,
) -> None:
    context = build_application_workspace_context(
        top_job_row=_job(),
        detail_text="We are looking for a Machine Learning Engineer with strong Python skills.",
        profile_row={"status": "approved", "payload_sha256": "a" * 64},
        fact_rows=[_fact()],
        document_rows=_documents(tmp_path),
        load_document=local_document_loader(private_root=tmp_path),
        as_of_date=date(2026, 9, 2),
    )

    assert context.generation_ready is True
    assert context.blocked_reasons == ()
    assert context.target.silver_job_id == 42
    assert [entry.fact_key for entry in context.claim_plan] == ["python"]
    assert context.claim_plan[0].job_references[0].evidence == "Python"
    assert context.application_authority is False
    assert context.submission_authority is False


def test_opaque_operator_document_reference_fails_closed(tmp_path: Path) -> None:
    rows = _documents(tmp_path)
    rows[0]["source_reference"] = "operator://cv/base"

    with pytest.raises(ApplicationWorkspaceStop, match="unsupported application source"):
        build_application_workspace_context(
            top_job_row=_job(),
            detail_text="Python",
            profile_row={"status": "approved", "payload_sha256": "a" * 64},
            fact_rows=[_fact()],
            document_rows=rows,
            load_document=local_document_loader(private_root=tmp_path),
            as_of_date=date(2026, 9, 2),
        )


def test_non_authoritative_job_remains_blocked_even_with_valid_private_sources(
    tmp_path: Path,
) -> None:
    job = _job()
    job["canonical_source_type"] = "aggregator"

    context = build_application_workspace_context(
        top_job_row=job,
        detail_text="Python",
        profile_row={"status": "approved", "payload_sha256": "a" * 64},
        fact_rows=[_fact()],
        document_rows=_documents(tmp_path),
        load_document=local_document_loader(private_root=tmp_path),
        as_of_date=date(2026, 9, 2),
    )

    assert context.generation_ready is False
    assert "employer_origin_required" in context.blocked_reasons
