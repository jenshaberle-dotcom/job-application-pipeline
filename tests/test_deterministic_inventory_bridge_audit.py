from __future__ import annotations

from scripts.run_deterministic_inventory_bridge_audit import classify_bridge, safe_url_shape


def _item() -> dict[str, object]:
    return {
        "candidate_id": 1,
        "company_key": "demo",
        "company_name": "Demo GmbH",
    }


def test_same_origin_career_link_is_reported_as_vocabulary_gap() -> None:
    html = '<html><body><a href="/karriere">Karriere</a></body></html>'
    result = classify_bridge(
        _item(),
        html=html,
        final_url="https://demo.example/",
        status=200,
    )

    assert "same_origin_listing_vocabulary_gap" in result["hypotheses"]
    assert result["same_origin_unclassified_count"] == 1


def test_explicit_canonical_workday_anchor_is_visible_without_granting_authority() -> None:
    html = """
    <html><body>
      <a href="https://example.wd3.myworkdayjobs.com/en-US/Careers">Open roles</a>
      <script>window.provider = 'myworkdayjobs.com';</script>
    </body></html>
    """
    result = classify_bridge(
        _item(),
        html=html,
        final_url="https://jobs.demo.example/",
        status=200,
    )

    carriers = result["carriers"]
    assert any(carrier["recognized_provider"] == "workday" for carrier in carriers)
    assert result["canonical_provider_anchor_count"] == 1


def test_safe_url_shape_never_persists_query_values() -> None:
    shape = safe_url_shape("https://example.test/jobs?id=secret-value&lang=de&id=other")

    assert shape == {
        "scheme": "https",
        "host": "example.test",
        "path": "/jobs",
        "query_keys": ["id", "lang"],
    }
    assert "secret-value" not in repr(shape)
    assert "other" not in repr(shape)
