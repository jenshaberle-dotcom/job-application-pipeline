from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROL_CENTER = ROOT / "scripts/run_product_v1_control_center.py"


def test_control_center_projects_origin_truth_without_inventing_cadence_authority() -> None:
    source = CONTROL_CENTER.read_text(encoding="utf-8")
    assert "project_demo_origin_truth" in source
    assert "project_demo_live_scope" not in source
    assert "DEFAULT_MAX_HEALTH_AGE_MINUTES" not in source
    assert '"employer_origin_url"' in source or "project_demo_origin_truth(" in source
    assert '"fixed_wall_clock_age_is_not_product_cadence_authority": True' in source
    assert '"exact_live_revalidation_occurs_at_f6_action_boundary": True' in source
    assert '"fresh_lifecycle_health_required_for_product_action": True' not in source
