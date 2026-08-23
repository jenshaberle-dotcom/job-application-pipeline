from __future__ import annotations

from io import BytesIO
import json

from scripts import product_v1_job_review_actions as actions
from scripts import run_product_v1_control_center as server


def _handler(path: str, payload: object | None = None):
    handler = object.__new__(server.ProductV1Handler)
    handler.path = path
    body = b"" if payload is None else json.dumps(payload).encode("utf-8")
    handler.headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
    }
    handler.rfile = BytesIO(body)
    responses: list[tuple[dict[str, object], object]] = []

    def send_json(payload: dict[str, object], *, status=200) -> None:
        responses.append((payload, status))

    handler._send_json = send_json  # type: ignore[method-assign]
    return handler, responses


def test_job_review_post_route_calls_exact_action_once(monkeypatch) -> None:
    calls: list[tuple[int, str]] = []

    def apply_action(*, silver_job_id: int, label: str):
        calls.append((silver_job_id, label))
        return {
            "status": "applied",
            "label_event": {"silver_job_id": silver_job_id, "label": label},
        }

    monkeypatch.setattr(server, "apply_job_review_label_action", apply_action)
    handler, responses = _handler(
        actions.JOB_REVIEW_LABEL_ACTION_PATH,
        {"silver_job_id": 42, "label": "interesting"},
    )

    handler.do_POST()

    assert calls == [(42, "interesting")]
    assert responses[0][0]["status"] == "applied"
    assert int(responses[0][1]) == 200


def test_job_review_post_rejects_forged_provenance_before_action(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        server,
        "apply_job_review_label_action",
        lambda **kwargs: calls.append(1),
    )
    handler, responses = _handler(
        actions.JOB_REVIEW_LABEL_ACTION_PATH,
        {
            "silver_job_id": 42,
            "label": "interesting",
            "job_evidence_fingerprint": "sha256:" + "0" * 64,
        },
    )

    handler.do_POST()

    assert calls == []
    assert responses[0][0]["status"] == "blocked"
    assert "job_evidence_fingerprint" in str(responses[0][0]["reason"])
    assert int(responses[0][1]) == 400


def test_job_review_post_reports_runtime_contract_block_without_write(monkeypatch) -> None:
    def fail_action(**kwargs):
        raise RuntimeError("job review label contract is not available in PostgreSQL")

    monkeypatch.setattr(server, "apply_job_review_label_action", fail_action)
    handler, responses = _handler(
        actions.JOB_REVIEW_LABEL_ACTION_PATH,
        {"silver_job_id": 42, "label": "unsure"},
    )

    handler.do_POST()

    assert responses[0][0]["status"] == "review_required"
    assert responses[0][0]["database_writes"] == 0
    assert responses[0][0]["provider_requests"] == 0
    assert responses[0][0]["product_authority"] is False
    assert int(responses[0][1]) == 409


def test_merge_job_review_labels_projects_latest_truth_without_authority() -> None:
    payload: dict[str, object] = {
        "summary": {"observed_job_count": 2},
        "job_readiness": [
            {"silver_job_id": 42, "title": "First"},
            {"silver_job_id": 43, "title": "Second"},
        ],
        "top_jobs": [{"silver_job_id": 42, "title": "First"}],
        "boundaries": {},
    }
    label_rows = [
        {
            "label_event_id": 91,
            "silver_job_id": 42,
            "label": "interesting",
            "reviewed_by": "operator",
            "reviewed_at": "2026-08-23T20:30:00Z",
            "evidence_cutoff": "2026-08-23T20:30:00Z",
            "job_evidence_fingerprint": "sha256:" + "a" * 64,
            "selection_reason": "normal_review",
            "capture_surface": "control_center",
            "deterministic_signal_visible": True,
            "ml_signal_visible": False,
            "llm_signal_visible": False,
            "supervised_target": 1,
            "training_eligible": True,
        }
    ]

    merged = server._merge_job_review_labels(
        payload,
        label_rows,
        capture_available=True,
    )

    jobs = merged["job_readiness"]
    assert jobs[0]["review_label"]["label"] == "interesting"  # type: ignore[index]
    assert jobs[1]["review_label"] is None  # type: ignore[index]
    assert merged["top_jobs"][0]["review_label"]["label_event_id"] == 91  # type: ignore[index]
    assert merged["summary"]["reviewed_job_count"] == 1  # type: ignore[index]
    assert merged["summary"]["training_eligible_review_label_count"] == 1  # type: ignore[index]
    assert merged["review_label_capture"]["available"] is True  # type: ignore[index]
    assert merged["review_label_capture"]["product_authority"] is False  # type: ignore[index]
    assert merged["boundaries"]["operator_review_labels_do_not_start_training"] is True  # type: ignore[index]
