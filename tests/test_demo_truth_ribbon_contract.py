from pathlib import Path


FRONTEND = Path("frontend/control-center/src")


def test_truth_ribbon_is_presentational_only() -> None:
    text = (FRONTEND / "DemoTruthRibbon.tsx").read_text(encoding="utf-8")
    main = (FRONTEND / "main.tsx").read_text(encoding="utf-8")

    assert "Live DB truth" in text
    assert "Review only" in text
    assert "No submit / send" in text
    assert "fetch(" not in text
    assert "/api/" not in text
    assert "DemoTruthRibbon" in main


def test_truth_ribbon_degrades_on_narrow_surfaces() -> None:
    css = (FRONTEND / "demo-truth-ribbon.css").read_text(encoding="utf-8")

    assert "@media (max-width: 1080px)" in css
    assert "@media (max-width: 760px)" in css
    assert ".demo-truth-ribbon { display: none; }" in css
