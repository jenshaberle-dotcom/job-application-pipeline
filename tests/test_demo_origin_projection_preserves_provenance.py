from pathlib import Path


def test_projection_contract_mentions_separate_discovery_provenance() -> None:
    source = Path(
        "src/search_intelligence/product_v1_demo_origin_projection.py"
    ).read_text(encoding="utf-8")
    assert "discovery_source_url" in source
