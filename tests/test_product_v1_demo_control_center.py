from __future__ import annotations

import pytest

from scripts.run_product_v1_demo_control_center import (
    DemoActionStop,
    parse_application_draft_action_payload,
    parse_f6_template_export_payload,
)


def test_application_draft_action_requires_exact_review_action() -> None:
    assert (
        parse_application_draft_action_payload(
            {
                "action": "generate_review_draft",
                "silver_job_id": 42,
                "request_id": "draft-test-001",
            }
        )
        == (42, "codex_quality", "draft-test-001")
    )
    assert (
        parse_application_draft_action_payload(
            {
                "action": "generate_review_draft",
                "silver_job_id": 42,
                "generation_mode": "local_private",
                "request_id": "draft-test-002",
            }
        )
        == (42, "local_private", "draft-test-002")
    )


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"action": "generate_review_draft"},
        {"action": "generate_review_draft", "silver_job_id": 42, "submit": True, "request_id": "draft-test-003"},
        {"action": "generate_review_draft", "silver_job_id": 42, "generation_mode": "remote_mystery", "request_id": "draft-test-004"},
        {"action": "submit_application", "silver_job_id": 42, "request_id": "draft-test-005"},
        {"action": "generate_review_draft", "silver_job_id": 0, "request_id": "draft-test-006"},
        {"action": "generate_review_draft", "silver_job_id": "not-an-id", "request_id": "draft-test-007"},
        {"action": "generate_review_draft", "silver_job_id": 42, "request_id": "x"},
        {"action": "generate_review_draft", "silver_job_id": 42, "request_id": "unsafe/request"},
    ],
)
def test_application_draft_action_rejects_widened_or_invalid_payload(payload: object) -> None:
    with pytest.raises(DemoActionStop):
        parse_application_draft_action_payload(payload)



def test_f6_export_action_requires_request_bound_progress_id() -> None:
    manifest = "a" * 64
    documents = {"base_cv": {}, "base_application_letter": {}}
    parsed = parse_f6_template_export_payload(
        {
            "action": "render_f6_review_package",
            "silver_job_id": 42,
            "source_manifest_sha256": manifest,
            "documents": documents,
            "request_id": "f6-export-001",
        }
    )

    assert parsed == (42, manifest, documents, "f6-export-001")

    with pytest.raises(DemoActionStop):
        parse_f6_template_export_payload(
            {
                "action": "render_f6_review_package",
                "silver_job_id": 42,
                "source_manifest_sha256": manifest,
                "documents": documents,
            }
        )
