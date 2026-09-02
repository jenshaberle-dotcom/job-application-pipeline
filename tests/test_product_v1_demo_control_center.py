from __future__ import annotations

import pytest

from scripts.run_product_v1_demo_control_center import (
    DemoActionStop,
    parse_application_draft_action_payload,
)


def test_application_draft_action_requires_exact_review_action() -> None:
    assert (
        parse_application_draft_action_payload(
            {"action": "generate_review_draft", "silver_job_id": 42}
        )
        == 42
    )


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"action": "generate_review_draft"},
        {"action": "generate_review_draft", "silver_job_id": 42, "submit": True},
        {"action": "submit_application", "silver_job_id": 42},
        {"action": "generate_review_draft", "silver_job_id": 0},
        {"action": "generate_review_draft", "silver_job_id": "not-an-id"},
    ],
)
def test_application_draft_action_rejects_widened_or_invalid_payload(payload: object) -> None:
    with pytest.raises(DemoActionStop):
        parse_application_draft_action_payload(payload)
