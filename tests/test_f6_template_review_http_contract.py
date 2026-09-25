from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "scripts" / "run_product_v1_demo_control_center.py"


def test_f6_c_loopback_export_is_manifest_bound_and_has_no_submit_send_authority() -> None:
    source = SERVER.read_text(encoding="utf-8")

    assert 'F6_TEMPLATE_REVIEW_PATH = "/api/v1/product-v1/f6-template-review"' in source
    assert 'F6_TEMPLATE_EXPORT_PATH = "/api/v1/product-v1/f6-template-export"' in source
    assert 'F6_TEMPLATE_EXPORT_PROGRESS_PATH = "/api/v1/product-v1/f6-template-export-progress"' in source
    assert "build_review_payload" in source
    assert "render_review_package" in source
    assert "combine_review_package" in source
    assert '"schema": "job_application_pipeline.f6_template_export.v2"' in source
    assert '"package": {' in source
    assert '"component_order": list(combined.component_order)' in source
    assert '"visual_identity": all(' in source
    assert "source_manifest_sha256" in source
    assert "draft source manifest is stale; regenerate review text before export" in source
    assert "_set_f6_export_progress" in source
    assert 'phase="render_templates"' in source
    assert 'phase="combine_pdf"' in source
    assert 'phase="build_word"' in source
    assert '"transport": "loopback_json_base64"' in source
    assert '"database_writes": 0' in source
    assert '"provider_requests": 0' in source
    assert '"application_actions": 0' in source
    assert '"submission_actions": 0' in source
    assert '"send_actions": 0' in source
    assert '"human_review_required": True' in source
    assert '"submission_authority": False' in source
    assert '"send_authority": False' in source
