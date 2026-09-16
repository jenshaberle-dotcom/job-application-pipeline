from pathlib import Path


SURFACE = Path("frontend/control-center/src/JobReviewLabelControls.tsx")


def test_f4b_operator_surface_names_affinity_and_target_alignment_distinctly() -> None:
    source = SURFACE.read_text(encoding="utf-8")

    assert 'label="Affinity"' in source
    assert '["Target-role alignment"' in source
    assert "Affinity components" in source
    assert "Target-role alignment is one weighted component" in source
    assert "Role affinity" not in source


def test_f4b_operator_surface_exposes_unknown_fit_and_combined_without_inventing_scores() -> None:
    source = SURFACE.read_text(encoding="utf-8")

    assert "Affinity · Job Fit · Combined" in source
    assert 'label="Job Fit"' in source
    assert 'label="Combined"' in source
    assert 'const fitPrimary = fitDecision === "passed"' in source
    assert '? "conflict"' not in source
    assert 'fitDecision === "failed"\n      ? "blocked"\n      : "?"' in source
    assert "numeric Candidate Fit is deferred to F4B-FOLLOWUP-001 / #891" in source
    assert "No Combined formula is authorized until numeric Fit is qualified" in source


def test_f4b_operator_surface_keeps_affinity_separate_from_fit_authority() -> None:
    source = SURFACE.read_text(encoding="utf-8")

    assert "Will ich diesen Job? Independent of Candidate Fit" in source
    assert "Affinity answers desirability only" in source
    assert "high Affinity cannot override it" in source
