from src.search_intelligence.native_census import population
from src.census_sources import hannover


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
