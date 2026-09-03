from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "control-center" / "src"


def test_operator_hardening_is_mounted_and_navigation_safe() -> None:
    main = (FRONTEND / "main.tsx").read_text(encoding="utf-8")
    guard = (FRONTEND / "DemoOperatorHardening.tsx").read_text(encoding="utf-8")

    assert 'import DemoOperatorHardening from "./DemoOperatorHardening";' in main
    assert "<DemoOperatorHardening />" in main
    assert 'document.addEventListener("click", onNavigationClick, true);' in guard
    assert 'document.addEventListener("keydown", onKeyDown);' in guard
    assert 'event.key !== "Escape"' in guard
    assert 'navigationButton.closest(".ow-data-layers-nav")' in guard
    assert 'document.body.classList.contains("data-layers-active")' in guard
    assert 'document.querySelector<HTMLButtonElement>(".ow-data-layers-nav button")' in guard
    assert "fetch(" not in guard
    assert "/api/" not in guard


def test_operator_hardening_preserves_active_surface_identity_and_motion_fallback() -> None:
    css = (FRONTEND / "demo-operator-hardening.css").read_text(encoding="utf-8")

    assert "body.data-layers-active .ow-topline > div > b::after" in css
    assert 'content: "Data Layers";' in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "animation: none !important;" in css
    assert "transition: none !important;" in css
