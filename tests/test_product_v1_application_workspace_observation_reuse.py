from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from scripts import product_v1_application_workspace_runtime as runtime
from src.search_intelligence.product_v1_application_context import (
    OPERATOR_SELECTED_AUTHORITY_SOURCE,
)


URL = "https://karriere.example.test/de?id=7879f1"


def _target(*, observation_url: str = URL) -> dict[str, object]:
    return {
        "silver_job_id": 626,
        "source_name": "generic_origin:example",
        "source_url": URL,
        "title": "AI Automation Engineer (m/w/d)",
        "company_name": "Example",
        "lifecycle_status": "active_confirmed",
        "last_health_checked_at": datetime.now(UTC).isoformat(),
        "latest_observation_source_url": observation_url,
        "latest_observation_evidence": {
            "source_url": observation_url,
            "raw_evidence": {
                "job": {
                    "source_url": observation_url,
                    "title": "AI Automation Engineer (m/w/d)",
                    "description": "Build production AI automation with Python and APIs.",
                },
                "source_specific": {
                    "employment": "Festanstellung",
                    "work_model": "Homeoffice",
                },
            },
        },
    }


def _runtime_rows(target: dict[str, object]):
    return (
        target,
        OPERATOR_SELECTED_AUTHORITY_SOURCE,
        {"status": "approved", "payload_sha256": "a" * 64},
        (),
        (),
    )


def test_workspace_reuses_exact_current_observation_without_network(monkeypatch) -> None:
    target = _target()
    monkeypatch.setattr(runtime, "_load_runtime_rows", lambda _job_id: _runtime_rows(target))
    monkeypatch.setattr(runtime, "_employer_origin_authorized", lambda _source: True)

    def no_network(_url: str):
        raise AssertionError("exact current observation must avoid redundant network fetch")

    monkeypatch.setattr(runtime, "fetch_public_https_detail_text", no_network)
    captured: dict[str, object] = {}

    def build_context(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(runtime, "build_application_workspace_context", build_context)

    context, final_url, title, evidence_mode, http_gets = runtime.load_application_workspace(626)

    assert isinstance(context, SimpleNamespace)
    assert final_url == URL
    assert title == "AI Automation Engineer (m/w/d)"
    assert evidence_mode == "exact_persisted_observation"
    assert http_gets == 0
    detail = str(captured["detail_text"])
    assert "Build production AI automation with Python and APIs." in detail
    assert "Festanstellung" in detail
    assert "Homeoffice" in detail


def test_workspace_falls_back_to_bounded_network_when_observation_binding_mismatches(
    monkeypatch,
) -> None:
    target = _target(observation_url="https://karriere.example.test/de?id=other")
    monkeypatch.setattr(runtime, "_load_runtime_rows", lambda _job_id: _runtime_rows(target))
    monkeypatch.setattr(runtime, "_employer_origin_authorized", lambda _source: True)
    calls: list[str] = []

    def network(url: str):
        calls.append(url)
        return url, "AI Automation Engineer (m/w/d)", "Current vacancy description"

    monkeypatch.setattr(runtime, "fetch_public_https_detail_text", network)
    monkeypatch.setattr(
        runtime,
        "build_application_workspace_context",
        lambda **_kwargs: SimpleNamespace(),
    )

    _context, final_url, title, evidence_mode, http_gets = runtime.load_application_workspace(626)

    assert calls == [URL]
    assert final_url == URL
    assert title == "AI Automation Engineer (m/w/d)"
    assert evidence_mode == "live_http_detail"
    assert http_gets == 1
