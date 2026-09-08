from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "control-center" / "src"
MAIN = SRC / "main.tsx"
ABOUT = SRC / "AboutPanel.tsx"
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
    assert '<i>ⓘ</i><span>About</span>' in about
    assert 'fetch("/app-info.json"' in about
    assert "desktop_version" in about
    assert "source_revision" in about
    assert "update_policy" in about
    assert "Internal diagnostic only" in about


def test_demo_pilot_badge_is_hidden_from_operator_header() -> None:
    css = _text(ABOUT_CSS)
    assert ".ow-topline > div > span" in css
    assert "display: none" in css


def test_live_launcher_publishes_exact_release_metadata_into_generated_dist() -> None:
    launcher = _text(LIVE_LAUNCHER)
    assert '"app-info.json"' in launcher
    assert '"desktop_version": desktop_version' in launcher
    assert '"source_revision": source_revision' in launcher
    assert '"desktop_host": "WebView2 WinForms"' in launcher
    assert '"runtime_surface": "WSL-backed local runtime"' in launcher
    assert '"data_truth": "PostgreSQL / DB-backed"' in launcher
    assert '"product_mode": "review-first"' in launcher
    assert 'compatibility.get("policy")' in launcher
    assert "JAP_APP_INFO=PASS" in launcher


def test_operator_surface_drops_preview_button_but_keeps_internal_preview_runtime() -> None:
    main = _text(MAIN)
    server = _text(CANONICAL_SERVER)
    assert "EvidencePreviewPanel" not in main
    assert '"/api/v1/product-v1/evidence-preview"' in server
    assert "load_downstream_evidence_preview_payload" in server


def test_bugfix_round_bumps_desktop_release() -> None:
    assert _text(VERSION).strip() == "1.0.8"
