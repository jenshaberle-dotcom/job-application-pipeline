from __future__ import annotations

from scripts.run_deterministic_successfactors_search_carrier_audit import (
    classify_search_script,
    explicit_root_get_search_forms,
    explicit_same_host_search_scripts,
)


def test_explicit_root_get_search_form_is_safe_and_value_free() -> None:
    html = """
    <html><body>
      <form method="get" action="/search/?locale=de_DE">
        <input name="q">
        <select name="country"></select>
      </form>
    </body></html>
    """
    forms = explicit_root_get_search_forms("https://jobs.example.invalid/", html)

    assert forms == (
        {
            "method": "get",
            "action": {
                "scheme": "https",
                "host": "jobs.example.invalid",
                "path": "/search/",
                "query_keys": ["locale"],
            },
            "field_names": ["country", "q"],
        },
    )


def test_cross_host_search_form_is_not_authorized() -> None:
    html = '<form method="get" action="https://other.invalid/search/"><input name="q"></form>'
    assert explicit_root_get_search_forms("https://jobs.example.invalid/", html) == ()


def test_exact_same_host_search_script_is_followable_without_persisting_query_values() -> None:
    html = """
    <script src="/platform/js/search/search.js?h=opaque-value"></script>
    <script src="https://cdn.example.invalid/platform/js/search/search.js?h=nope"></script>
    """
    scripts = explicit_same_host_search_scripts("https://jobs.example.invalid/", html)

    assert scripts == (
        "https://jobs.example.invalid/platform/js/search/search.js?h=opaque-value",
    )


def test_other_same_host_scripts_do_not_qualify() -> None:
    html = '<script src="/platform/js/j2w/min/j2w.core.min.js?h=x"></script>'
    assert explicit_same_host_search_scripts("https://jobs.example.invalid/", html) == ()


def test_script_get_route_requires_explicit_get_binding() -> None:
    evidence = classify_search_script(
        'var cfg={type:"GET",url:"/search/?currentPage=1&pageSize=15"};'
    )

    assert evidence["classification"] == "explicit_script_get_search_route"
    assert evidence["strict_get_search_route_shapes"] == [
        {"path": "/search/", "query_keys": ["currentPage", "pageSize"]}
    ]
    assert evidence["post_method_observed_near_search_route"] is False


def test_script_route_without_method_does_not_claim_get() -> None:
    evidence = classify_search_script('var url="/search/";')

    assert evidence["classification"] == "search_route_literal_without_strict_get_binding"
    assert evidence["strict_get_search_route_shapes"] == []


def test_script_post_near_route_fails_closed_for_get_classification() -> None:
    evidence = classify_search_script(
        'var cfg={type:"POST",url:"/search/?q=secret"};'
    )

    assert evidence["classification"] == "search_route_literal_without_strict_get_binding"
    assert evidence["strict_get_search_route_shapes"] == []
    assert evidence["post_method_observed_near_search_route"] is True
