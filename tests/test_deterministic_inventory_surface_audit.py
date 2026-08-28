from __future__ import annotations

from scripts.run_deterministic_inventory_surface_audit import classify_surface


def _item() -> dict[str, object]:
    return {
        "candidate_id": 1,
        "company_key": "demo",
        "company_name": "Demo GmbH",
    }


def test_external_jobish_anchor_is_visible_when_not_promoted() -> None:
    html = """
    <html><body>
      <a href="https://jobs.other-example.com/careers">Zum Jobportal</a>
    </body></html>
    """
    result = classify_surface(
        _item(),
        html=html,
        final_url="https://demo.example/karriere",
        status=200,
    )
    assert "external_jobish_anchor_not_promoted" in result["signals"]
    assert result["external_jobish_anchor_count"] == 1


def test_same_origin_jobish_anchor_not_classified_is_visible() -> None:
    # Plain /career + "Karriere" is visibly job/career-related, but is not one
    # of the existing strict listing URL/text markers. The audit must report
    # that gap without changing production navigation authority.
    html = """
    <html><body>
      <a href="/career">Karriere</a>
    </body></html>
    """
    result = classify_surface(
        _item(),
        html=html,
        final_url="https://demo.example/about",
        status=200,
    )
    assert "same_origin_jobish_anchor_not_classified" in result["signals"]
    assert result["same_origin_jobish_anchor_count"] == 1
    assert result["navigation_candidate_count"] == 0


def test_form_and_client_script_signals_are_reported() -> None:
    html = """
    <html><body>
      <form method="post" action="/career/search"></form>
      <script src="/_next/static/chunks/jobs.js"></script>
    </body></html>
    """
    result = classify_surface(
        _item(),
        html=html,
        final_url="https://demo.example/karriere",
        status=200,
    )
    assert "form_driven_inventory_surface" in result["signals"]
    assert "client_rendered_or_script_inventory_surface" in result["signals"]
    assert result["post_form_count"] == 1
