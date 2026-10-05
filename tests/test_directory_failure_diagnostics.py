import json
import subprocess
from pathlib import Path
from urllib.error import HTTPError

import pytest

from scripts import discover_configured_directory as configured
from scripts import discover_munich_startups as munich
from src.search_intelligence.public_directory_discovery import (
    discovery_failure,
    unique_page_heading,
)


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 503])
def test_child_http_failure_preserves_status_without_raw_error(status):
    error = subprocess.CalledProcessError(1, ["secret_command"], stderr=(
        "Traceback: /private/path\n"
        f"urllib.error.HTTPError: HTTP Error {status}: secret-token-private-message\n"))
    result = discovery_failure(error)
    assert result == {"exit_code": 1, "http_status": status, "failure_reason": "HTTP_ERROR"}
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize("tail,reason", [
    ("urllib.error.URLError: Name or service not known", "DNS_FAILURE"),
    ("urllib.error.URLError: Temporary failure in name resolution", "DNS_FAILURE"),
    ("SSL: CERTIFICATE_VERIFY_FAILED", "TLS_CERTIFICATE_FAILURE"),
    ("TimeoutError: timed out", "TRANSPORT_TIMEOUT"),
    ("ModuleNotFoundError: No module named 'private'", "RUNTIME_IMPORT_FAILURE"),
    ("ValueError: directory_record_identity_not_found", "SOURCE_IDENTITY_PARSE_FAILURE"),
    ("unrecognized private message", "SUBPROCESS_FAILED"),
])
def test_child_failure_is_classified_without_leaking_message(tail, reason):
    result = discovery_failure(subprocess.CalledProcessError(1, ["private"], stderr=tail))
    assert result["failure_reason"] == reason
    assert "private" not in json.dumps(result)


def test_quoted_source_code_does_not_fake_http_diagnosis():
    error = subprocess.CalledProcessError(1, ["cmd"], stderr=(
        '    raise ValueError("HTTP Error 403")\n'
        "RuntimeError: a different error\n"))
    assert discovery_failure(error)["failure_reason"] == "SUBPROCESS_FAILED"


def test_timeout_and_json_failure_do_not_publish_raw_output():
    error = subprocess.TimeoutExpired(["private"], 240, output="private", stderr="secret")
    assert discovery_failure(error) == {"failure_reason": "SOURCE_TIMEOUT"}
    error = json.JSONDecodeError("private", "secret", 1)
    assert discovery_failure(error) == {"failure_reason": "INVALID_SOURCE_JSON"}
    assert discovery_failure(OSError("private")) == {"failure_reason": "SOURCE_IO_FAILURE"}
    assert discovery_failure(ValueError("private")) == {"failure_reason": "SOURCE_SHAPE_FAILURE"}


def test_bytes_and_empty_child_stderr():
    assert discovery_failure(subprocess.CalledProcessError(1, ["cmd"], stderr=(
        b"HTTP Error 404: private")))["http_status"] == 404
    assert discovery_failure(subprocess.CalledProcessError(1, ["cmd"])) == {
        "failure_reason": "SUBPROCESS_FAILED", "exit_code": 1}


def test_original_brigk_event_is_not_a_company(monkeypatch):
    config = json.loads(Path("contracts/discovery/ingolstadt-digital.json").read_text())
    observed_event = '<a href="https://www.brigk.digital/brigk-air-startup-opportunities">Startup Opportunities: Dual-Use Innovation</a>'
    monkeypatch.setattr(configured, "fetch_text", lambda *args: observed_event)
    assert configured.discover(config)["companies"] == []


@pytest.mark.parametrize("html", ["", "<h1></h1>", "<h1>First</h1><h1>Other</h1>",
                                  "<h1>Page not found</h1>", "<h1>https://example.com</h1>"])
def test_profile_requires_one_actual_unambiguous_heading(html):
    with pytest.raises(ValueError, match="directory_profile_heading_"):
        unique_page_heading(html)


def test_profile_heading_never_includes_whole_card_or_script():
    assert unique_page_heading('<h1>Acme <span>&amp; Co</span><script>private</script></h1>'
                               '<p>Long startup description</p>') == "Acme & Co"
    assert unique_page_heading('<h1>Acme</h1><h1>Acme</h1>') == "Acme"


def listing(*slugs):
    # Synthetic structure with real observed URL namespace; not captured live HTML.
    return "".join(f'<a href="/en/startups-and-ecosystem/{slug}">'
                   'A long card description, not the company name</a>' for slug in slugs)


def test_munich_migrated_namespace_and_name_from_profile(monkeypatch):
    calls = []

    def fetch(url, *, timeout):
        calls.append(url)
        assert timeout == 8
        return listing("acme") if url == munich.SOURCE.start_url else "<h1>Actual Acme GmbH</h1>"

    monkeypatch.setattr(munich, "fetch_text", fetch)
    result = munich.discover(delay=0)
    assert result["company_count"] == 1
    assert result["companies"][0]["company_name"] == "Actual Acme GmbH"
    assert result["companies"][0]["website"] is None
    assert result["complete"] is False
    assert result["pagination_status"] == "UNQUALIFIED_LOAD_MORE"
    assert len(calls) == 2
    assert all("paging=" not in url and "/startups/" not in url for url in calls)


def test_munich_link_identity_is_origin_and_path_bound():
    html = listing("acme") + "".join(f'<a href="{href}">not a profile</a>' for href in (
        "https://evil.example/en/startups-and-ecosystem/stolen",
        "/en/events/test", "/en/startups-and-ecosystem",
        "/en/startups-and-ecosystem/acme?secret=x", "/en/startups-and-ecosystem/acme#x",
        "http://www.munich-startup.de/en/startups-and-ecosystem/insecure",
    ))
    assert munich.profile_urls(html) == [munich.SOURCE.start_url + "/acme"]


def test_munich_partial_profile_failure_preserves_good_rows(monkeypatch):
    def fetch(url, **kwargs):
        if url == munich.SOURCE.start_url:
            return listing("good", "bad")
        return "<h1>Actual Company</h1>" if url.endswith("/good") else "<h1>Page not found</h1>"

    monkeypatch.setattr(munich, "fetch_text", fetch)
    result = munich.discover(delay=0)
    assert result["company_count"] == 1
    assert len(result["profile_failures"]) == 1
    assert result["complete"] is False


def test_munich_empty_listing_is_parse_failure_not_empty_market(monkeypatch):
    monkeypatch.setattr(munich, "fetch_text", lambda *a, **k: "<h1>Startups</h1>")
    with pytest.raises(ValueError, match="directory_record_identity_not_found"):
        munich.discover(delay=0)


def test_munich_detail_cap_prevents_unbounded_requests(monkeypatch):
    calls = []

    def fetch(url, **kwargs):
        calls.append(url)
        return listing(*(f"item-{i}" for i in range(50))) if url == munich.SOURCE.start_url else "<h1>Company</h1>"

    monkeypatch.setattr(munich, "fetch_text", fetch)
    result = munich.discover(delay=0)
    assert len(calls) == 25
    assert result["visible_profile_count"] == 50
    assert result["profile_request_count"] == 24
    assert result["complete"] is False
    with pytest.raises(ValueError, match="bounds"):
        munich.discover(delay=0, max_profiles=25)


def test_direct_profile_http_failure_retains_code_without_message():
    error = HTTPError("https://private.example?token=private", 429, "secret", {}, None)
    assert discovery_failure(error) == {"http_status": 429, "failure_reason": "HTTP_ERROR"}
