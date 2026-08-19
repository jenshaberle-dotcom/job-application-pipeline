from pathlib import Path

from src.search_intelligence.product_v1_service import build_product_v1_payload
from src.search_intelligence.source_connector_overview import (
    empty_source_connector_overview,
)


API = Path("scripts/run_product_v1_control_center.py")
APP = Path("frontend/control-center/src/App.tsx")
FINAL_APPROVAL_DIALOG = Path(
    "frontend/control-center/src/FinalApprovalReviewDialog.tsx"
)


def test_product_payload_embeds_read_only_source_connector_overview() -> None:
    overview = empty_source_connector_overview()
    payload = build_product_v1_payload(
        wave_states=[],
        job_readiness=[],
        top_jobs=[],
        ranking_policy={"status": "approved"},
        hard_filter_policy={"status": "approved"},
        application_readiness=[],
        application_sources=[],
        migration_ready=True,
        source_connector_overview=overview,
    )

    assert payload["source_connector_overview"] == overview
    assert payload["source_connector_overview"]["boundaries"] == {
        "read_only": True,
        "no_source_activation": True,
        "no_ingestion": True,
        "no_scheduler_mutation": True,
        "unknown_is_not_success": True,
        "registration_is_not_activation": True,
    }


def test_source_connector_endpoint_is_read_only() -> None:
    source = API.read_text(encoding="utf-8")

    assert 'parsed.path == "/api/v1/source-connectors"' in source
    assert "load_source_connector_overview_payload" in source
    assert "build_source_connector_overview" in source
    assert "def do_POST" in source
    assert "METHOD_NOT_ALLOWED" in source
    assert "subprocess" not in source


def test_react_overview_names_all_distinct_lifecycle_stages() -> None:
    source = APP.read_text(encoding="utf-8")

    assert "Source & connector lifecycle" in source
    assert "Employer-origin truth" in source
    assert '["implementation", "Implemented"]' in source
    assert '["validation", "Validated"]' in source
    assert '["final_approval", "Approved"]' in source
    assert '["registration", "Registered"]' in source
    assert '["activation", "Activated"]' in source
    assert '["ingestion", "Ingested"]' in source
    assert "No connector registration or activation" in source
    assert "No reviewed mutation available" in source
    assert "activateSource" not in source


def test_final_approval_ui_reuses_only_the_reviewed_3a_action_and_refetches_truth() -> None:
    app = APP.read_text(encoding="utf-8")
    dialog = FINAL_APPROVAL_DIALOG.read_text(encoding="utf-8")

    assert "candidate_id: number | null" in app
    assert 'source.current_blocker === "final_approval_incomplete"' in app
    assert "FinalApprovalReviewDialog" in app
    assert 'fetch("/api/v1/product-v1"' in app

    assert (
        'FINAL_APPROVAL_ACTION_PATH = "/api/v1/source-connectors/final-approval"'
        in dialog
    )
    assert (
        'FINAL_APPROVAL_CONFIRMATION = "approve_final_registration_gate"'
        in dialog
    )
    assert 'source.current_blocker !== "final_approval_incomplete"' in dialog
    assert "candidate_id: candidateId" in dialog
    assert "confirmation: FINAL_APPROVAL_CONFIRMATION" in dialog
    assert "await refreshProductTruth()" in dialog
    assert "Evidence" in dialog
    assert "Boundary" in dialog
    assert "Confirmation" in dialog
    assert "approval_token" not in dialog
    assert "activateSource" not in dialog
