from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend" / "control-center" / "src" / "JobReviewLabelControls.tsx"


def test_pending_candidate_fit_is_summarized_once_not_repeated_per_fact() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'return "candidate fit not fully assessed"' in source
    assert 'return "fit evidence missing"' not in source
    assert "const resolvedFitLabel = fitLabel(fit);" in source
    assert "{resolvedFitLabel && <em" in source


def test_resolved_dimension_fit_remains_visible() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'if (status === "passed") return "match";' in source
    assert 'if (status === "failed") return "conflict";' in source
    assert 'if (status === "passed") return "fit confirmed";' in source
    assert 'if (status === "failed") return "fit conflict";' in source


def test_origin_truth_dimensions_remain_unchanged() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    for label in (
        "Location & work model",
        "Skills & capabilities",
        "Level & experience",
        "Employment & language",
    ):
        assert label in source

    assert "Candidate Fit remains a separate authority." in source
