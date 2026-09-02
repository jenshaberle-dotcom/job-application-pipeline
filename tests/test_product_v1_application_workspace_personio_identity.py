from __future__ import annotations

from datetime import date
from hashlib import sha256
from pathlib import Path

from src.search_intelligence.product_v1_application_workspace import (
    build_application_workspace_context,
    local_document_loader,
)


def test_application_target_uses_reviewed_personio_employer_brand(tmp_path: Path) -> None:
    documents = []
    for document_type, content in (
        ("base_cv", "CV structure"),
        ("base_application_letter", "Letter structure"),
    ):
        path = tmp_path / f"{document_type}.txt"
        path.write_text(content, encoding="utf-8")
        documents.append(
            {
                "document_type": document_type,
                "source_label": document_type,
                "source_reference": f"local://{path.name}",
                "content_sha256": sha256(content.encode("utf-8")).hexdigest(),
                "status": "approved",
            }
        )

    context = build_application_workspace_context(
        top_job_row={
            "silver_job_id": 434,
            "product_rank": 1,
            "title": "(Junior) Data Engineer - Data Platform (m/f/d)",
            "company_name": "Heartbeat AI GmbH",
            "source_name": "personio:1komma5grad",
            "source_url": "https://1komma5grad.jobs.personio.de/job/2731150?language=de",
            "canonical_source_type": "unknown",
            "product_readiness_status": "rankable",
            "origin_validation_status": "validated",
            "activity_status": "active",
            "hard_filter_status": "passed",
        },
        detail_text="Python data platform role",
        profile_row={"status": "approved", "payload_sha256": "a" * 64},
        fact_rows=[
            {
                "fact_key": "python",
                "category": "skill",
                "evidence_class": "professional_employment",
                "approval_status": "approved",
                "statement": "I use Python professionally.",
                "capability_tags": ["Python"],
                "limitations": [],
                "valid_from": None,
                "valid_until": None,
            }
        ],
        document_rows=documents,
        load_document=local_document_loader(private_root=tmp_path),
        as_of_date=date(2026, 9, 2),
        employer_origin_authorized=True,
    )

    assert context.generation_ready is True
    assert context.target.company_name == "1KOMMA5°"
