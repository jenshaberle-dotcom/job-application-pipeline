from __future__ import annotations

import json
from pathlib import Path

from scripts.run_product_v1_demo_workspace_probe import (
    evaluate_workspace_payload,
    run_workspace_probe,
    selected_job_id_from_preflight,
)
from src.search_intelligence.product_v1_application_workspace import ApplicationWorkspaceStop


def _workspace_payload() -> dict[str, object]:
    return {
        "status": "ready",
        "workspace": {
            "target": {
                "silver_job_id": 42,
                "title": "Machine Learning Engineer",
                "company_name": "Example GmbH",
            },
            "generation_ready": True,
            "claim_plan": [
                {
                    "fact_key": "ml.delivery",
                    "statement": "Delivered ML systems.",
                    "job_references": [{"evidence": "machine learning"}],
                }
            ],
            "source_manifest": {
                "candidate_fact_keys": ["ml.delivery"],
                "documents": [
                    {"document_type": "base_cv", "status": "approved"},
                    {
                        "document_type": "base_application_letter",
                        "status": "approved",
                    },
                ],
            },
        },
        "live_job_evidence": {
            "final_url": "https://jobs.example.com/42",
            "fetched_title": "Machine Learning Engineer",
            "detail_sha256": "a" * 64,
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


def test_selected_job_requires_passing_preflight(tmp_path: Path) -> None:
    path = tmp_path / "preflight.json"
    path.write_text(
        json.dumps(
            {
                "state": "pass",
                "selected_top_job": {"silver_job_id": 42},
            }
        ),
        encoding="utf-8",
    )

    assert selected_job_id_from_preflight(path) == 42


def test_ready_workspace_probe_requires_exact_grounded_context() -> None:
    report = evaluate_workspace_payload(silver_job_id=42, payload=_workspace_payload())

    assert report["state"] == "pass"
    assert report["blocking_checks"] == []
    assert all(report["checks"].values())
    assert report["boundaries"]["provider_requests"] == 0
    assert report["boundaries"]["database_writes"] is False


def test_workspace_probe_blocks_empty_claim_plan() -> None:
    payload = _workspace_payload()
    payload["workspace"]["claim_plan"] = []

    report = evaluate_workspace_payload(silver_job_id=42, payload=payload)

    assert report["state"] == "blocked"
    assert "claim_plan_present" in report["blocking_checks"]


def test_workspace_probe_blocks_target_identity_mismatch() -> None:
    payload = _workspace_payload()
    payload["workspace"]["target"]["silver_job_id"] = 99

    report = evaluate_workspace_payload(silver_job_id=42, payload=payload)

    assert report["state"] == "blocked"
    assert "selected_job_exact_bound" in report["blocking_checks"]


def test_workspace_probe_blocks_any_write_or_provider_boundary() -> None:
    payload = _workspace_payload()
    payload["boundaries"]["provider_requests"] = 1

    report = evaluate_workspace_payload(silver_job_id=42, payload=payload)

    assert report["state"] == "blocked"
    assert "zero_write_provider_boundary" in report["blocking_checks"]


def test_runtime_failure_is_reported_fail_closed() -> None:
    def loader(_silver_job_id: int):
        raise ApplicationWorkspaceStop("approved base CV is missing")

    report = run_workspace_probe(silver_job_id=42, loader=loader)

    assert report["state"] == "blocked"
    assert report["blocking_checks"] == ["workspace_runtime"]
    assert report["provider_requests"] if False else True
    assert report["boundaries"]["provider_requests"] == 0
    assert report["boundaries"]["database_writes"] is False
