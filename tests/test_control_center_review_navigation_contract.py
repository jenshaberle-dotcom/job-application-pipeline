from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "frontend" / "control-center" / "src" / "OperatorWorkspace.tsx"
ORIGIN_PROJECTION = (
    ROOT
    / "src"
    / "search_intelligence"
    / "product_v1_demo_origin_projection.py"
)


def test_review_navigation_falls_back_to_exact_discovery_url() -> None:
    workspace = WORKSPACE.read_text(encoding="utf-8")
    assert "discovery_source_url?: string | null;" in workspace
    assert "job.source_url || job.discovery_source_url" in workspace
    assert "Open original ↗" in workspace


def test_application_origin_guard_stays_separate_from_review_navigation() -> None:
    projection = ORIGIN_PROJECTION.read_text(encoding="utf-8")
    assert 'copied["discovery_source_url"] = discovery_url' in projection
    assert 'copied["employer_origin_url"] = guard.employer_origin_url' in projection
    assert 'copied["source_url"] = guard.employer_origin_url' in projection
