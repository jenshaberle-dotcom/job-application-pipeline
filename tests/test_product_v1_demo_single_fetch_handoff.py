from __future__ import annotations

from datetime import date
from hashlib import sha256

from scripts import run_product_v1_demo_workspace_probe as workspace_probe
from scripts.run_product_v1_demo_draft_handoff import evaluate_handoff
from src.search_intelligence.product_v1_application_context import (
    ApplicationSourceDocumentSnapshot,
    ApplicationTargetSnapshot,
    CandidateFactSnapshot,
    build_product_v1_application_context,
)


DETAIL = "Data Engineer role. We need Python and SQL for reliable data pipelines."


def _document(kind: str) -> ApplicationSourceDocumentSnapshot:
    content = f"{kind} style source only"
    return ApplicationSourceDocumentSnapshot(
        document_type=kind,
        source_label=kind,
        source_reference=f"local://{kind}",
        content_sha256=sha256(content.encode("utf-8")).hexdigest(),
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


def test_workspace_single_fetch_carries_final_review_package(monkeypatch) -> None:
    calls = []

    def loader(silver_job_id: int):
        calls.append(silver_job_id)
        return _context(), "https://jobs.example.com/42", "Data Engineer"

    monkeypatch.setattr(workspace_probe, "load_application_workspace", loader)
    report = workspace_probe.run_workspace_probe_single_fetch(silver_job_id=42)

    assert calls == [42]
    assert report["state"] == "pass"
    assert report["boundaries"]["job_detail_http_gets"] == 1
    assert report["checks"]["evidence_first_draft_built"] is True
    carried = report["evidence_first_draft"]
    assert carried["draft_mode"] == "deterministic_evidence_first"
    assert carried["provider_requests"] == 0
    assert carried["database_writes"] == 0
    assert carried["submission_writes"] == 0
    assert carried["package"]["status"] == "draft_for_review"


def _handoff_report() -> dict[str, object]:
    context = _context()
    package = workspace_probe.build_evidence_first_review_draft(context)
    workspace_payload = {
        "status": "ready",
        "workspace": context.canonical_payload(),
        "live_job_evidence": {
            "final_url": "https://jobs.example.com/42",
            "fetched_title": "Data Engineer",
            "detail_sha256": context.target.detail_sha256,
        },
        "boundaries": {
            "database_reads": True,
            "database_writes": False,
            "job_detail_http_gets": 1,
            "provider_requests": 0,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
        },
    }
    report = workspace_probe.evaluate_workspace_payload(
        silver_job_id=42,
        payload=workspace_payload,
    )
    report["evidence_first_draft"] = {
        "draft_mode": "deterministic_evidence_first",
        "package": package.canonical_payload(),
        "detail_sha256": context.target.detail_sha256,
        "provider_requests": 0,
        "database_writes": 0,
        "application_writes": 0,
        "submission_writes": 0,
        "send_actions": 0,
    }
    return report


def test_draft_handoff_is_artifact_only_and_exact_bound() -> None:
    report = _handoff_report()
    report["preflight_artifact_sha256"] = "c" * 64

    draft = evaluate_handoff(
        silver_job_id=42,
        report=report,
        expected_preflight_sha256="c" * 64,
        workspace_artifact_sha256="d" * 64,
    )

    assert draft["state"] == "pass"
    assert draft["preflight_artifact_sha256"] == "c" * 64
    assert draft["workspace_artifact_sha256"] == "d" * 64
    assert draft["boundaries"]["workspace_job_detail_http_gets"] == 1
    assert draft["boundaries"]["draft_probe_http_gets"] == 0
    assert draft["boundaries"]["database_reads"] == 0
    assert draft["boundaries"]["provider_requests"] == 0
    assert all(draft["checks"].values())


def test_draft_handoff_rejects_preflight_artifact_mismatch() -> None:
    report = _handoff_report()
    report["preflight_artifact_sha256"] = "c" * 64

    draft = evaluate_handoff(
        silver_job_id=42,
        report=report,
        expected_preflight_sha256="e" * 64,
    )

    assert draft["state"] == "blocked"
    assert "preflight_artifact_exact_bound" in draft["blocking_checks"]


def test_draft_handoff_rejects_detail_fingerprint_mismatch() -> None:
    context = _context()
    package = workspace_probe.build_evidence_first_review_draft(context)
    report = {
        "state": "pass",
        "silver_job_id": 42,
        "workspace": context.canonical_payload(),
        "live_job_evidence": {"detail_sha256": context.target.detail_sha256},
        "boundaries": {"job_detail_http_gets": 1},
        "evidence_first_draft": {
            "package": package.canonical_payload(),
            "detail_sha256": "b" * 64,
            "provider_requests": 0,
            "database_writes": 0,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
        },
    }

    draft = evaluate_handoff(silver_job_id=42, report=report)

    assert draft["state"] == "blocked"
    assert "live_detail_fingerprint_bound" in draft["blocking_checks"]
