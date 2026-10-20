import json
from urllib.error import HTTPError

import pytest

from src.census_sources import brigk, public_directory, stuttgart, munich


def test_stuttgart_reads_published_map_not_navigation():
    rows = [dict(id=1, title="Employer &amp; Co", type=["unternehmen"],
                 url="https://employer.example", permalink="https://directory.example/1"),
            dict(id=2, title="Research institute", type=["forschung"])]
    result = stuttgart.parse_directory('var dmMapData = ' + json.dumps({"companies": rows}) + ";")
    assert result["complete"] and result["company_count"] == 1
    assert result["companies"][0]["company_name"] == "Employer & Co"
    with pytest.raises(ValueError, match="empty"):
        stuttgart.parse_directory('var dmMapData = {"companies":[]};')


def test_brigk_keeps_domain_evidence_and_marks_missing_logos():
    html = ('Overview of our startups</h2><a href="https://startup.example"><img src="logo.png"></a>'
            '<img src="unidentified.png"><h2>Building</h2><a href="https://landlord.example"><img></a>')
    result = brigk.parse_directory(html)
    assert result["company_count"] == 1 and not result["complete"]
    assert result["companies"][0]["identity_kind"] == "DOMAIN_ONLY"
    assert result["companies"][0]["company_name_verified"] is False
    assert result["unidentified_logos"] == 1


def test_read_retries_are_bounded_and_access_denial_not_retried(monkeypatch):
    calls = []
    def timeout(*a, **kw):
        calls.append(1)
        raise TimeoutError()
    monkeypatch.setattr(public_directory, "_fetch_text", timeout)
    monkeypatch.setattr(public_directory.time, "sleep", lambda _: None)
    with pytest.raises(TimeoutError):
        public_directory.fetch_text("https://example.org")
    assert len(calls) == 3
    calls.clear()
    def denied(*a, **kw):
        calls.append(1)
        raise HTTPError("https://example.org", 403, "denied", {}, None)
    monkeypatch.setattr(public_directory, "_fetch_text", denied)
    with pytest.raises(HTTPError):
        public_directory.fetch_text("https://example.org")
    assert len(calls) == 1


def test_munich_checkpoint_survives_later_page_failure(monkeypatch):
    page = dict(startups=[dict(id="1", slug="one", title="One")], totalCount=2,
                cursor="1", hasNextPage=True)
    responses = iter([json.dumps(page), TimeoutError()])
    def fetch(*a, **kw):
        value = next(responses)
        if isinstance(value, Exception):
            raise value
        return value
    monkeypatch.setattr(munich, "fetch_text", fetch)
    saved = []
    with pytest.raises(TimeoutError):
        munich.discover(delay=0, checkpoint=saved.append)
    assert len(saved) == 1
    assert not saved[0]["complete"] and saved[0]["company_count"] == 1
