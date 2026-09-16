from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts/run_product_v1_demo_control_center.py"
MAIN = ROOT / "frontend/control-center/src/main.tsx"
SURFACE = ROOT / "frontend/control-center/src/F4cSourceHealthSurface.tsx"
STYLE = ROOT / "frontend/control-center/src/f4c-source-health-surface.css"


def test_installed_product_payload_uses_current_source_health_projection() -> None:
    source = RUNTIME.read_text(encoding="utf-8")

    assert "project_current_source_health" in source
    assert "load_source_schedule_evidence" in source
    assert "def _load_operator_product_payload" in source
    assert "self._send_json(_load_operator_product_payload())" in source


def test_source_health_surface_is_mounted_and_names_separate_truth_dimensions() -> None:
    main = MAIN.read_text(encoding="utf-8")
    surface = SURFACE.read_text(encoding="utf-8")

    assert 'import F4cSourceHealthSurface from "./F4cSourceHealthSurface"' in main
    assert "<F4cSourceHealthSurface />" in main
    for label in (
        "Current health & scheduling",
        "Latest run",
        "Run age",
        "Scheduling",
        "Cadence",
        "Next expected run",
        "Reachability now",
        "Last yield",
        "Zero-yield success",
    ):
        assert label in surface
    assert "A historical successful run is run history only" in surface
    assert "current reachability remains unknown until actually measured" in surface


def test_redundant_operations_and_data_layer_source_health_surfaces_are_hidden() -> None:
    surface = SURFACE.read_text(encoding="utf-8")
    style = STYLE.read_text(encoding="utf-8")

    assert '.includes("Operations")' in surface
    assert 'wrapper.dataset.f4cHidden = "true"' in surface
    assert '[data-f4c-hidden="true"]' in style
    assert ".data-layers-screen .dl-source-card" in style
    assert "display: none !important" in style


def test_surface_is_read_only_and_does_not_create_new_operator_actions() -> None:
    surface = SURFACE.read_text(encoding="utf-8")

    assert "readProductTruth" in surface
    assert "fetch(" not in surface
    assert "POST" not in surface
    assert "application-draft" not in surface
    assert "source_activation" not in surface
