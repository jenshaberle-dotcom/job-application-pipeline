from __future__ import annotations

from scripts.create_standard_workflow_handover import (
    MINIMAL_RESTART_PAYLOAD_SCHEMA_VERSION,
    build_minimal_restart_payload,
)


def test_build_minimal_restart_payload_is_compact_and_safety_bounded() -> None:
    payload = build_minimal_restart_payload(
        git={
            "branch": "main",
            "head": "abc123 Add example",
            "dirty": False,
        },
        completed_work_items=[
            "STATE-001A",
            "INSPECT-001A",
            "HANDOVER-001A",
            "RULES-001A",
            "VALIDATE-001A",
            "NEXT-001A",
        ],
        recommended_next=[
            "SENSOR-001E BA Remote/Nationwide Bounded Sample Execution Review",
        ],
        next_report={
            "standard_workflow_completion": {
                "present_in_head_count": 6,
                "required_count": 6,
                "percent_in_head": 100.0,
            },
            "horizontal_freeze_path_bundle_mode": {
                "mode_id": "FREEZE-001A",
                "available": True,
            },
            "next_safe_action": {
                "action": "return_to_product_pipeline_work_with_explicit_work_item",
                "workstream": "search_intelligence_product_work",
                "work_item": "SENSOR-001E BA Remote/Nationwide Bounded Sample Execution Review",
            },
        },
        validate_report={
            "profile": "commit",
            "overall_status": "pass",
            "required_failure_count": 0,
            "optional_warning_count": 0,
        },
        rules_path="docs/reference/governance/workflow/rules001_project_rules_index.md",
    )

    assert payload["schema_version"] == MINIMAL_RESTART_PAYLOAD_SCHEMA_VERSION
    assert payload["required_new_chat_artifacts"] == ["handover_json", "handover_zip"]
    assert payload["repo"]["head"] == "abc123 Add example"
    assert payload["validation"]["overall_status"] == "pass"
    assert payload["recommended_next"] == [
        "SENSOR-001E BA Remote/Nationwide Bounded Sample Execution Review",
    ]
    assert payload["safety_boundary"]["requires_system_impact_analysis_before_patch"] is True
    assert payload["safety_boundary"]["requires_explicit_approval_before_external_or_product_action"] is True
    assert payload["safety_boundary"]["no_database_writes"] is True
