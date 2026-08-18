from __future__ import annotations

from scripts import run_product_v1_control_center_preview as preview_server


DETAIL = (
    "Data Engineer. Permanent employment. Hybrid work model. Fluent German and English. "
    "35-40 hours per week. We require a senior-level professional. Build data pipelines with SQL."
)


def _row():
    return {
        "silver_job_id": 42,
        "title": "Data Engineer",
        "company_name": "Example GmbH",
        "source_url": "https://jobs.example.com/42",
        "canonical_source_type": "employer_origin",
        "origin_validation_status": "validated",
        "activity_status": "active",
        "product_readiness_status": "hard_filter_decision_required",
        "employment_type": "unknown",
        "employment_evidence_status": "unknown",
        "required_languages": [],
        "language_evidence_status": "unknown",
        "weekly_hours_min": None,
        "weekly_hours_max": None,
        "weekly_hours_evidence_status": "unknown",
        "work_model": "unknown",
        "title_seniority": "unknown",
        "requirements_seniority": "unknown",
        "seniority_evidence_status": "unknown",
        "capability_fit_status": "unknown",
        "capability_fit_evidence_status": "unknown",
        "profile_direction_score": None,
        "data_focus_score": None,
        "reliability_focus_score": None,
        "evidence_quality_score": None,
    }


def test_preview_loader_reads_one_job_fetches_one_detail_and_never_calls_provider(monkeypatch) -> None:
    calls: list[str] = []

    def load_job(silver_job_id: int):
        calls.append(f"db:{silver_job_id}")
        return _row()

    def fetch_detail(source_url: str):
        calls.append(f"detail:{source_url}")
        return source_url, "Data Engineer | Example", DETAIL

    monkeypatch.setattr(preview_server, "_load_preview_job", load_job)
    monkeypatch.setattr(preview_server, "fetch_public_https_detail_text", fetch_detail)

    payload = preview_server.load_downstream_evidence_preview_payload(42)

    assert calls == ["db:42", "detail:https://jobs.example.com/42"]
    assert payload["status"] == "preview_ready"
    assert payload["target"]["silver_job_id"] == 42
    assert payload["boundaries"]["provider_requests"] == 0
    assert payload["boundaries"]["database_writes"] == 0
    assert payload["boundaries"]["hard_filter_authority"] is False
    assert payload["boundaries"]["ranking_authority"] is False
    assert payload["capability_fit_review"]["review_required"] is True
    assert payload["capability_fit_review"]["auto_pass_from_tag_overlap"] is False


def test_preview_loader_blocks_before_detail_fetch_when_origin_authority_is_missing(monkeypatch) -> None:
    row = _row()
    row["origin_validation_status"] = "pending"
    calls: list[str] = []

    monkeypatch.setattr(preview_server, "_load_preview_job", lambda _job_id: row)
    monkeypatch.setattr(
        preview_server,
        "fetch_public_https_detail_text",
        lambda _url: calls.append("unexpected"),
    )

    try:
        preview_server.load_downstream_evidence_preview_payload(42)
    except Exception as exc:
        assert type(exc).__name__ == "DownstreamPreviewStop"
        assert "validated origin" in str(exc)
    else:
        raise AssertionError("missing origin authority must block preview")

    assert calls == []
