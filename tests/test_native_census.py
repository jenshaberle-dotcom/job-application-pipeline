from src.search_intelligence.native_census import population
from src.census_sources import hannover
from scripts.run_native_census_campaign import Progress, source_error
import json
import ssl
from urllib.error import URLError
import pytest
from scripts import run_native_census_campaign as campaign


def test_all_regions_missing_websites_and_raw_observations_retained():
    snapshots = {"a": {"companies": [
        {"company_name": "München GmbH", "website": "https://example.org", "location": "München"},
        {"company_name": "Berlin AG", "location": "Berlin"},
        {"company_name": "", "location": "unknown"}]},
        "b": {"companies": [{"company_name": "München GmbH", "website": "https://example.org"}]}}
    result = population(snapshots)
    assert result["candidate_count"] == 2
    assert len(result["rejected"]) == 1
    assert sum(len(r["observations"]) for r in result["candidates"]) == 3
    assert not result["personal_relevance_filter_applied"]


def test_large_population_is_not_truncated():
    result = population({"source": {"companies": [{"company_name": f"Company {n}"} for n in range(1735)]}})
    assert result["candidate_count"] == 1735
    assert result["factory_batch_count"] == 18


def test_hannover_source_keeps_nonlocal_nontech_companies(monkeypatch):
    monkeypatch.setattr(hannover, "fetch_page", lambda *a: "1 Firmen gefunden")
    monkeypatch.setattr(hannover, "parse_company_blocks", lambda *a: [
        {"company_name": "Other employer", "location": "10115 Berlin", "fields": ["Other"],
         "source_record_id": "123", "website": "", "directory_url": "https://example.org/123"}])
    result = hannover.discover(1, 0, 1)
    assert result["company_count"] == 1
    assert result["companies"][0]["location"] == "10115 Berlin"


def test_hannover_compact_and_full_views_merge_only_same_identity():
    html = """<a href="/companies/123/">Employer</a>
    <a href="/companies/123/">Employer</a>
    <p>Anschrift</p><p>10115 Berlin</p><p>Berufsfeld(er)</p><p>Other</p>
    <p>Homepage</p><p>https://example.org</p>"""
    rows = hannover.parse_company_blocks(html)
    assert len(rows) == 1
    assert rows[0]["website"] == "https://example.org"
    assert rows[0]["location"] == "10115 Berlin"


def test_progress_has_liveness_and_explicit_failure(tmp_path):
    try:
        with Progress(tmp_path) as p:
            p.update(phase="ASSESSING", completed=3, total=10)
            value = json.loads(p.path.read_text())
            assert value["completed"] == 3 and value["updated_at"] >= value["last_progress_at"]
            raise ValueError("fixture")
    except ValueError:
        pass
    value = json.loads((tmp_path / "native-progress.json").read_text())
    assert value["phase"] == "FAILED" and value["error_code"] == "ValueError"


def test_tls_error_is_categorized_without_exposing_raw_log(tmp_path):
    path = tmp_path / "log"
    path.write_text("private text CERTIFICATE_VERIFY_FAILED")
    assert source_error(path) == "TLS_CERTIFICATE_INVALID"


def test_tls_probe_does_not_swallow_certificate_failure(monkeypatch):
    def fail(*args, **kwargs):
        assert kwargs["context"].check_hostname
        assert kwargs["context"].verify_mode == ssl.CERT_REQUIRED
        raise URLError(ssl.SSLCertVerificationError("untrusted"))
    monkeypatch.setattr(campaign, "urlopen", fail)
    with pytest.raises(URLError):
        campaign.verify_tls()
