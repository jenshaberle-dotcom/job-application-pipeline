from __future__ import annotations

from scripts.run_deterministic_detail_surface_audit import classify_detail_surface


def test_unknown_identifier_like_query_key_is_visible_without_value_persistence() -> None:
    html = """
    <html><body>
      <a href="/stellenangebote?we_objectID=123456">Data Engineer (m/w/d)</a>
    </body></html>
    """
    result = classify_detail_surface(
        page_url="https://jobs.example.invalid/stellenangebote",
        html=html,
        status=200,
    )

    assert result["classification"] == "unknown_query_identifier_key_surface"
    assert result["unknown_identifier_query_keys"] == {"weobjectid": 1}


def test_current_trusted_query_identifier_wins_over_gap_diagnostics() -> None:
    html = """
    <html><body>
      <a href="/jobs?jobid=ABCD1234">Data Engineer (m/w/d)</a>
    </body></html>
    """
    result = classify_detail_surface(
        page_url="https://jobs.example.invalid/jobs",
        html=html,
        status=200,
    )

    assert result["classification"] == "strict_query_detail_already_visible"
    assert result["trusted_query_detail_count"] == 1
    assert result["unknown_identifier_query_keys"] == {}


def test_client_rendered_surface_is_visible_without_inventing_detail_route() -> None:
    html = """
    <html><body>
      <div id="app"></div>
      <script src="/_next/static/chunks/jobs.js"></script>
      <script>window.__NEXT_DATA__ = {"page":"jobs"};</script>
    </body></html>
    """
    result = classify_detail_surface(
        page_url="https://careers.example.invalid/jobs",
        html=html,
        status=200,
    )

    assert result["classification"] == "client_rendered_or_script_detail_surface"
    assert result["trusted_query_detail_count"] == 0
    assert result["unknown_identifier_query_keys"] == {}


def test_form_driven_detail_signal_reports_field_names_not_values() -> None:
    html = """
    <html><body>
      <form method="post" action="/jobs/detail">
        <input type="hidden" name="candidateObjectId" value="SECRET-VALUE">
      </form>
    </body></html>
    """
    result = classify_detail_surface(
        page_url="https://jobs.example.invalid/jobs",
        html=html,
        status=200,
    )

    assert result["classification"] == "form_driven_detail_surface"
    assert result["forms"][0]["field_names"] == ["candidateObjectId"]
    assert "SECRET-VALUE" not in str(result)
