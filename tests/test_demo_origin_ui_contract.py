from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "frontend/control-center/src/OperatorWorkspace.tsx"
PROJECTION = ROOT / "src/search_intelligence/product_v1_demo_origin_projection.py"


def test_operator_workspace_action_link_consumes_projected_source_url() -> None:
    source = WORKSPACE.read_text(encoding="utf-8")
    projection = PROJECTION.read_text(encoding="utf-8")
    assert "job.source_url" in source
    assert 'copied["source_url"] = guard.employer_origin_url' in projection
    assert 'copied["discovery_source_url"] = discovery_url' in projection


def test_backend_projection_is_the_aggregator_action_boundary() -> None:
    projection = PROJECTION.read_text(encoding="utf-8")
    assert "evaluate_demo_origin_guard" in projection
    assert "Legacy consumers use source_url as the clickable Product action target" in projection
