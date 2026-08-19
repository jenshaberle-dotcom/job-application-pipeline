from __future__ import annotations

from http import HTTPStatus

from scripts import product_v1_downstream_preview_runtime as preview_runtime
from scripts import run_product_v1_control_center as canonical_server


DETAIL = (
    "Data Engineer. Permanent employment. Hybrid work model. Fluent German and English. "
    "35-40 hours per week. We require a senior-level professional. Build data pipelines with SQL."
)


def _row() -> dict[str, object]:
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


def _handler(path: str):
    handler = object.__new__(canonical_server.ProductV1Handler)
    handler.path = path
    responses: list[tuple[dict[str, object], HTTPStatus]] = []

    def send_json(
        payload: dict[str, object],
        *,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        responses.append((payload, status))

    handler._send_json = send_json  # type: ignore[method-assign]
    return handler, responses


def test_canonical_handler_serves_read_only_evidence_preview(monkeypatch) -> None:
    calls: list[int] = []

    def load_preview(silver_job_id: int) -> dict[str, object]:
        calls.append(silver_job_id)
        return {
            "status": "preview_ready",
            "boundaries": {
                "provider_requests": 0,
                "database_writes": 0,
                "product_authority": False,
            },
        }

    monkeypatch.setattr(
        canonical_server,
        "load_downstream_evidence_preview_payload",
        load_preview,
    )
    handler, responses = _handler(
        "/api/v1/product-v1/evidence-preview?silver_job_id=42"
    )

    handler.do_GET()

    assert calls == [42]
    assert responses == [
        (
            {
                "status": "preview_ready",
                "boundaries": {
                    "provider_requests": 0,
                    "database_writes": 0,
                    "product_authority": False,
                },
            },
            HTTPStatus.OK,
        )
    ]


def test_canonical_preview_query_fails_closed_before_loader(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        canonical_server,
        "load_downstream_evidence_preview_payload",
        lambda silver_job_id: calls.append(silver_job_id),
    )
    handler, responses = _handler(
        "/api/v1/product-v1/evidence-preview?silver_job_id=not-an-integer"
    )

    handler.do_GET()

    assert calls == []
    assert responses[0][1] == HTTPStatus.BAD_REQUEST
    assert responses[0][0]["status"] == "blocked"
    assert responses[0][0]["provider_requests"] == 0
    assert responses[0][0]["database_writes"] == 0
    assert responses[0][0]["product_authority"] is False


def test_canonical_handler_preserves_post_block_outside_reviewed_action() -> None:
    handler, responses = _handler("/api/v1/product-v1")

    handler.do_POST()

    assert responses == [
        (
            {
                "status": "blocked",
                "reason": "Product V1 POST route is not in the reviewed action allowlist.",
            },
            HTTPStatus.METHOD_NOT_ALLOWED,
        )
    ]
    # The canonical GET loader may add read-only projections such as structured
    # locations. POST authority remains independently and explicitly allowlisted.
    assert canonical_server.ProductV1Handler.do_POST is not canonical_server._base.ProductV1Handler.do_POST


def test_shared_preview_runtime_is_provider_free_and_authority_gated(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(preview_runtime, "_load_preview_job", lambda job_id: _row())
    monkeypatch.setattr(
        preview_runtime,
        "fetch_public_https_detail_text",
        lambda source_url: (
            calls.append(source_url) or source_url,
            "Data Engineer | Example",
            DETAIL,
        ),
    )

    payload = preview_runtime.load_downstream_evidence_preview_payload(42)

    assert calls == ["https://jobs.example.com/42"]
    assert payload["status"] == "preview_ready"
    assert payload["boundaries"]["provider_requests"] == 0
    assert payload["boundaries"]["database_writes"] == 0
    assert payload["boundaries"]["product_authority"] is False


def test_shared_preview_runtime_blocks_before_fetch_without_origin_authority(
    monkeypatch,
) -> None:
    row = _row()
    row["origin_validation_status"] = "pending"
    calls: list[str] = []
    monkeypatch.setattr(preview_runtime, "_load_preview_job", lambda job_id: row)
    monkeypatch.setattr(
        preview_runtime,
        "fetch_public_https_detail_text",
        lambda source_url: calls.append(source_url),
    )

    try:
        preview_runtime.load_downstream_evidence_preview_payload(42)
    except preview_runtime.DownstreamPreviewStop as exc:
        assert "validated origin" in str(exc)
    else:
        raise AssertionError("missing origin authority must block preview")

    assert calls == []
