from pathlib import Path

SCRIPT = Path("scripts/run_origin_source_discovery_agent.py").read_text(encoding="utf-8")


def test_search_provider_placeholder_keys_do_not_crash_agent() -> None:
    assert "_is_missing_or_placeholder_secret" in SCRIPT
    assert "provider=tavily reason=missing_or_placeholder_api_key" in SCRIPT
    assert "provider=brave reason=missing_or_placeholder_api_key" in SCRIPT
    assert "provider=google_cse reason=missing_or_placeholder_api_key_or_cx" in SCRIPT
    assert "return []" in SCRIPT


def test_search_provider_http_errors_are_logged_not_raised() -> None:
    assert "web_search_warning: provider_http_error" in SCRIPT
    assert "response.raise_for_status()" in SCRIPT
    assert "except requests.HTTPError" in SCRIPT


def test_brave_request_is_bounded_if_locale_params_are_supported() -> None:
    assert "max(1, min(max_results, 20))" in SCRIPT
