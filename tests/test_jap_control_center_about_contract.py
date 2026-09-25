from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "control-center" / "src"
MAIN = SRC / "main.tsx"
ABOUT = SRC / "AboutPanel.tsx"
DATA_LAYERS = SRC / "DataLayersTab.tsx"
ABOUT_CSS = SRC / "about-panel.css"
LIVE_LAUNCHER = ROOT / "scripts" / "run_product_v1_live_demo.py"
CANONICAL_SERVER = ROOT / "scripts" / "run_product_v1_control_center.py"
VERSION = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "VERSION"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_about_is_operator_tab_with_installed_app_identity() -> None:
    main = _text(MAIN)
    about = _text(ABOUT)

    assert 'import AboutPanel from "./AboutPanel";' in main
    assert "<AboutPanel />" in main
    assert 'document.querySelector<HTMLElement>(".ow-sidebar nav")' in about
    assert 'document.querySelector<HTMLElement>(".ow-main")' in about
    assert "new MutationObserver(" in about
    assert "attempts < 80" not in about
    assert '<i>ⓘ</i><span>About</span>' in about
    assert 'fetch("/app-info.json"' in about
    assert "desktop_version" in about
    assert "source_revision" in about
    assert "update_policy" in about
    assert "Internal diagnostic only" in about
    assert "Integrated self-update" in about
    assert "Prompted inside this app" in about
    assert '<div><span>Compatibility line</span><b>{value(info?.compatibility_line, "unknown")}</b></div>' in about
    assert 'v{value(info?.compatibility_line' not in about


def test_dynamic_operator_tabs_wait_for_workspace_without_time_budget() -> None:
    about = _text(ABOUT)
    data_layers = _text(DATA_LAYERS)

    for source in (about, data_layers):
        assert "new MutationObserver(" in source
        assert "observer.observe(document.body, { childList: true, subtree: true })" in source
        assert "observer?.disconnect()" in source
        assert "attempts < 80" not in source
        assert "window.setTimeout(bindRoots, 50)" not in source


def test_demo_pilot_badge_is_hidden_from_operator_header() -> None:
    css = _text(ABOUT_CSS)
    assert ".ow-topline > div > span" in css
    assert "display: none" in css


def test_live_launcher_publishes_exact_release_metadata_into_generated_dist() -> None:
    launcher = _text(LIVE_LAUNCHER)
    assert 'FRONTEND_SOURCE_MARKER = ".jap-source-sha"' in launcher
    assert 'os.environ.get("JAP_CONTROL_CENTER_PINNED_SHA"' in launcher
    assert "_write_frontend_source_marker" in launcher
    assert "_assert_reusable_frontend_source" in launcher
    assert '"app-info.json"' in launcher
    assert '"desktop_version": desktop_version' in launcher
    assert '"source_revision": source_revision' in launcher
    assert '"desktop_host": "WebView2 WinForms"' in launcher
    assert '"runtime_surface": "WSL-backed local runtime"' in launcher
    assert '"data_truth": "PostgreSQL / DB-backed"' in launcher
    assert '"product_mode": "review-first"' in launcher
    assert 'compatibility.get("policy")' in launcher
    assert "JAP_APP_INFO=PASS" in launcher


def test_installed_runtime_does_not_block_startup_on_external_demo_probe() -> None:
    launcher = _text(LIVE_LAUNCHER)
    assert '"--installed-runtime"' in launcher
    assert "if args.installed_runtime:" in launcher
    installed_start = launcher.index("if args.installed_runtime:")
    preflight_start = launcher.index("preflight_output = _demo_artifact_path")
    assert installed_start < preflight_start
    assert "JAP_INSTALLED_RUNTIME_NETWORK=startup_local_only" in launcher
    assert "JAP_INSTALLED_RUNTIME_BOUNDARY=no_auto_submit,no_send,no_startup_provider" in launcher


def test_operator_surface_drops_preview_button_but_keeps_internal_preview_runtime() -> None:
    main = _text(MAIN)
    server = _text(CANONICAL_SERVER)
    assert "EvidencePreviewPanel" not in main
    assert '"/api/v1/product-v1/evidence-preview"' in server
    assert "load_downstream_evidence_preview_payload" in server


def test_current_product_local_release_version() -> None:
    assert _text(VERSION).strip() == "1.1.12"


def test_failed_python_frontend_prewarm_surface_is_removed() -> None:
    launcher = _text(LIVE_LAUNCHER)

    assert '"--prepare-frontend-only"' not in launcher
    assert "args.prepare_frontend_only" not in launcher
    assert "JAP_FRONTEND_PREPARE=PASS" not in launcher
