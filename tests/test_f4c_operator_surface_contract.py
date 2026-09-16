from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts/run_product_v1_demo_control_center.py"
MAIN = ROOT / "frontend/control-center/src/main.tsx"
SURFACE = ROOT / "frontend/control-center/src/F4cSourceHealthSurface.tsx"
STYLE = ROOT / "frontend/control-center/src/f4c-source-health-surface.css"
DATA_LAYERS = ROOT / "frontend/control-center/src/DataLayersTab.tsx"


def test_installed_product_payload_uses_current_source_health_projection() -> None:
    source = RUNTIME.read_text(encoding="utf-8")

    assert "project_current_source_health" in source
    assert "load_source_schedule_evidence" in source
    assert "def _load_operator_product_payload" in source
    assert "self._send_json(_load_operator_product_payload())" in source


def test_source_surface_answers_operator_questions_without_cadence_jargon() -> None:
    main = MAIN.read_text(encoding="utf-8")
    surface = SURFACE.read_text(encoding="utf-8")

    assert 'import F4cSourceHealthSurface from "./F4cSourceHealthSurface"' in main
    assert "<F4cSourceHealthSurface />" in main
    for label in (
        "Source status & job delivery",
        "Latest source scan",
        "Current jobs",
        "Last job delivery",
        "Source data age",
        "Gone since previous successful scan",
        "Live now",
        "Latest scan yield",
        "Recurring ingestion",
    ):
        assert label in surface
    for rejected in (
        "Since last attempt",
        "Expected interval",
        "Next expected attempt",
        "no expected interval is defined",
        "Current health & scheduling",
    ):
        assert rejected not in surface
    assert "it is not a live ping" in surface
    assert "Not comparable yet" in surface


def test_redundant_operations_and_data_layer_source_health_surfaces_are_removed() -> None:
    surface = SURFACE.read_text(encoding="utf-8")
    style = STYLE.read_text(encoding="utf-8")
    data_layers = DATA_LAYERS.read_text(encoding="utf-8")

    assert '.includes("Operations")' in surface
    assert 'wrapper.dataset.f4cHidden = "true"' in surface
    assert '[data-f4c-hidden="true"]' in style
    assert "dl-source-card" not in data_layers
    assert "Source contribution" not in data_layers
    assert "Last run" not in data_layers


def test_data_layers_uses_one_current_population_and_omits_repeat_observation_chart() -> None:
    data_layers = DATA_LAYERS.read_text(encoding="utf-8")

    assert "one population" in data_layers
    assert "exact current <b>All jobs</b> population" in data_layers
    assert "Every stage below uses the same current population" in data_layers
    assert "Layer flow · current cohort" in data_layers
    assert "Repeat source sightings are intentionally not plotted here" in data_layers
    assert "bronze_observations" not in data_layers
    assert "Persisted inventory" not in data_layers
    assert "persisted Gold outside current All jobs" not in data_layers


def test_surface_is_read_only_and_does_not_create_new_operator_actions() -> None:
    surface = SURFACE.read_text(encoding="utf-8")

    assert "readProductTruth" in surface
    assert "fetch(" not in surface
    assert "POST" not in surface
    assert "application-draft" not in surface
    assert "source_activation" not in surface
