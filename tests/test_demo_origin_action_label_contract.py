from pathlib import Path


def test_origin_projection_removes_discovery_url_from_action_slot() -> None:
    source = Path(
        "src/search_intelligence/product_v1_demo_origin_projection.py"
    ).read_text(encoding="utf-8")
    assert 'copied["source_url"]' in source
    assert "employer_origin_url" in source
