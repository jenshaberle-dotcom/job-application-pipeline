"""Offline regression cases: discovery must work without a legacy DB identity."""
import argparse
import pytest
from scripts import run_origin_source_discovery_agent_v4 as discovery
from scripts import run_deterministic_connector_builder_layer_audit as layers


def test_census_identity_reaches_discovery_without_database(monkeypatch):
    seen = {}
    monkeypatch.setattr(discovery, "connect", lambda: pytest.fail("Unexpected database lookup"))
    monkeypatch.setattr(discovery, "collect_search_results", lambda *a, **kw: [])
    monkeypatch.setattr(discovery, "generate_company_url_candidates_v2", lambda **kw: [])
    def discover(**kwargs):
        seen.update(kwargs)
        return {}
    monkeypatch.setattr(discovery, "discover_origin_source", discover)
    monkeypatch.setattr(discovery, "result_to_json", lambda result: {
        "decision": "origin_url_candidate_selected", "selected_url": "https://example.org",
    })
    monkeypatch.setattr(layers, "run_origin_discovery", discovery.run_for_company)
    args = argparse.Namespace(target_location="", origin_timeout_seconds=5,
                              origin_max_candidates=12)
    url, evidence = layers._resolve_origin(
        {"id": 99, "company_key": "census-abc", "company_name": "Example GmbH"}, args)
    assert url == "https://example.org"
    assert seen["company_name"] == "Example GmbH"
    assert seen["company_key"] == "census-abc"
    assert evidence["provider_requests"] == 0


@pytest.mark.parametrize("identity", [
    {}, {"company_key": "other", "company_name": "Example"},
    {"company_key": "census-abc", "company_name": ""},
    {"company_key": "census-abc", "company_name": None},
])
def test_invalid_identity_does_not_fall_back_to_another_database_record(monkeypatch, identity):
    monkeypatch.setattr(discovery, "connect", lambda: pytest.fail("Unexpected database lookup"))
    with pytest.raises(ValueError, match="INVALID_CANDIDATE_IDENTITY_HANDOFF"):
        discovery.run_for_company(argparse.Namespace(candidate_identity=identity), "census-abc")


def test_persisted_url_does_not_trigger_discovery(monkeypatch):
    monkeypatch.setattr(layers, "run_origin_discovery", lambda *a: pytest.fail("Unexpected discovery"))
    url, _ = layers._resolve_origin(
        {"company_key": "example", "candidate_url": "https://example.org"}, None)
    assert url == "https://example.org"


@pytest.mark.parametrize("key", ["census-"+"a"*64, "b"*64, "123e4567-e89b-12d3-a456-426614174000"])
def test_storage_identifiers_never_become_domains_or_identity_evidence(key):
    from src.search_intelligence.origin_candidate_plan_v2 import generate_company_url_candidates_v2
    from src.search_intelligence.origin_source_discovery_agent import company_identity_tokens
    tokens=company_identity_tokens(company_key=key,company_name="Example GmbH")
    assert tokens == ("example",)
    candidates=generate_company_url_candidates_v2(company_key=key,company_name="Example GmbH",max_candidates=12)
    assert candidates
    assert all("example" in c.url and key not in c.url and "census" not in c.url for c in candidates)
