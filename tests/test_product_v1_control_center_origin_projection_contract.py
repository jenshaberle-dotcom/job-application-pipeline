from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROL_CENTER = ROOT / "scripts/run_product_v1_control_center.py"


def test_control_center_projects_demo_origin_truth() -> None:
    source = CONTROL_CENTER.read_text(encoding="utf-8")
    assert "project_demo_origin_truth" in source
    assert '"employer_origin_url"' in source or "project_demo_origin_truth(" in source
