import copy

import pytest

from src.search_intelligence.cloud_census_import import digest, plan_import, validate_export


def export():
    population = {
        "schema_version": "jap_cloud.fresh_connector_population.v1",
        "provenance": {"cloud_repository_sha": "a" * 40},
        "summary": {"employer_candidate_count": 3},
        "candidates": [
            {"company_key": "a", "company_name": "München GmbH", "geographies": ["MUNICH"],
             "websites": ["https://example.org"], "discovery_evidence_ids": ["source:a"]},
            {"company_key": "b", "company_name": "Berlin GmbH",
             "websites": [], "discovery_evidence_ids": ["source:b"]},
            {"company_key": "c", "company_name": "Hannover GmbH",
             "discovery_evidence_ids": ["source:c"]},
        ],
    }
    return {"schema_version": "jap.cloud_census_export.v1", "population": population,
            "population_digest": digest(population), "census_run": "cloud-census:test",
            "sql_readback_verified": True}


def test_all_regions_and_missing_websites_preserved():
    value = export()
    before = copy.deepcopy(value)
    plan = plan_import(value, [])
    assert plan["candidate_count"] == 3
    assert plan["counts"] == {"CREATED_DISCOVERY": 3}
    assert not plan["geography_filter_applied"]
    assert plan["sources_activated"] == 0
    assert value == before
    assert [r["observation"] for r in plan["candidates"]] == value["population"]["candidates"]


def test_identity_collision_is_review_not_overwrite():
    plan = plan_import(export(), [{"id": 7, "company_key": "different", "company_name": "Berlin GmbH"},
                                 {"id": 8, "company_key": "c", "company_name": "Hannover GmbH"}])
    assert plan["counts"] == {"CREATED_DISCOVERY": 1, "IDENTITY_REVIEW": 1, "EXISTING": 1}
    assert plan["candidates"][2]["classic_candidate_id"] == 8


@pytest.mark.parametrize("change", ["digest", "count", "duplicate", "lineage", "proof"])
def test_incomplete_or_changed_exports_rejected(change):
    value = export()
    if change == "digest":
        value["population"]["candidates"][0]["company_name"] = "Changed"
    elif change == "count":
        value["population"]["summary"]["employer_candidate_count"] = 4
    elif change == "duplicate":
        value["population"]["candidates"][1]["company_key"] = "a"
    elif change == "lineage":
        value["population"]["candidates"][0]["discovery_evidence_ids"] = []
    else:
        value["sql_readback_verified"] = False
    if change != "digest":
        value["population_digest"] = digest(value["population"])
    with pytest.raises(ValueError):
        validate_export(value)


def test_same_name_inside_population_is_not_silently_merged():
    value = export()
    value["population"]["candidates"][1]["company_name"] = "München GmbH"
    value["population_digest"] = digest(value["population"])
    plan = plan_import(value, [])
    assert plan["candidates"][1]["disposition"] == "IDENTITY_REVIEW"
