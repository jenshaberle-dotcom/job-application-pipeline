from pathlib import Path


SURFACE = Path("frontend/control-center/src/JobReviewLabelControls.tsx")


def test_f4b_operator_surface_names_affinity_and_target_alignment_distinctly() -> None:
    source = SURFACE.read_text(encoding="utf-8")

    assert '? "Affinity preview" : "Affinity"' in source
    assert '["Target-role alignment"' in source
    assert "Affinity components" in source
    assert "Target-role alignment is one weighted component" in source
    assert "Role affinity" not in source


def test_f4b_operator_surface_exposes_numeric_skill_fit_but_no_combined_score() -> None:
    source = SURFACE.read_text(encoding="utf-8")

    assert "Affinity · Candidate Fit · Combined" in source
    assert 'label="Candidate Fit"' in source
    assert 'label="Combined"' in source
    assert 'candidate_fit_authority_status === "authoritative"' in source
    assert "observed job skills are evidenced by approved CV/Candidate Facts" in source
    assert "Geography, seniority and hard requirements are separate gates." in source
    assert 'fitDecision === "failed"\n      ? "blocked"\n      : "?"' in source
    assert "No Combined formula is authorized. Candidate Fit and Affinity remain separate decision signals." in source


def test_f4b_operator_surface_keeps_affinity_separate_from_fit_authority() -> None:
    source = SURFACE.read_text(encoding="utf-8")

    assert "Will ich diesen Job? Independent of Candidate Fit" in source
    assert "Affinity answers desirability only" in source
    assert "high Affinity cannot override it" in source
