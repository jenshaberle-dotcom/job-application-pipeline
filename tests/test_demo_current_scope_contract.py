from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FOCUS = ROOT / "docs/status/current/DEMO-001-P0-FOCUS.md"


def test_demo_focus_requires_live_origin_truth_before_rankable_five() -> None:
    text = FOCUS.read_text(encoding="utf-8")
    assert "Employer-Origin" in text
    assert "freshly live-verifiable" in text
    assert "at least five real" in text
    assert "No fabricated scores" in text
