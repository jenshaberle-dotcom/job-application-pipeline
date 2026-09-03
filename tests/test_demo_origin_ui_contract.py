from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "frontend/control-center/src/OperatorWorkspace.tsx"


def test_operator_workspace_uses_employer_origin_action_url() -> None:
    source = WORKSPACE.read_text(encoding="utf-8")
    assert "employer_origin_url" in source
    assert "demo_actionable" in source
    assert "Discovery only" in source
    assert "Open employer origin" in source


def test_operator_workspace_does_not_synthesize_ba_as_original_job() -> None:
    source = WORKSPACE.read_text(encoding="utf-8")
    assert "arbeitsagentur.de/jobsuche/jobdetail" not in source
    assert "ba://" not in source
