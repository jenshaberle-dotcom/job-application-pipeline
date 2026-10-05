from copy import deepcopy

import pytest

from src.search_intelligence.discovery_coverage import assess


def candidate(name="Acme", geography="REGION_HANNOVER"):
    return {"company_name": name, "geographies": [geography], "cohorts": ["TECH"]}


def test_coverage_gap_requests_more_sources_without_blocking_factory_learning():
    result = assess({"candidates": [candidate()]})
    assert result["status"] == "SOURCE_COVERAGE_GAP"
    assert result["coverage_gaps"]["BERLIN"]["additional_sources_required"] is True
    assert result["factory_run_recommended"] is True
    assert result["ml_scale_ready"] is False


def test_broad_population_passes_scale_gate():
    candidates = []
    limits = {
        "REGION_HANNOVER": 250,
        "WOLFSBURG": 50,
        "INGOLSTADT": 50,
        "STUTTGART_REGION": 100,
        "BERLIN": 250,
        "MUNICH": 250,
    }
    for geography, count in limits.items():
        candidates.extend(candidate(f"Acme {geography} {index}", geography) for index in range(count))
    result = assess({"candidates": candidates})
    assert result["status"] == "PASS"
    assert result["ml_scale_ready"] is True


@pytest.mark.parametrize("name", ["Homepage", "Name", "http://acme.example", "www.acme.example", "", None])
def test_corrupt_names_are_not_recommended_for_factory_or_ml(name):
    census = {"candidates": [candidate(name)]}
    before = deepcopy(census)
    result = assess(census)
    assert result["status"] == "SOURCE_IDENTITY_INVALID"
    assert result["identity_errors"]
    assert result["counts_are_unvalidated_observations"] is True
    assert result["factory_run_recommended"] is False
    assert result["ml_scale_ready"] is False
    assert census == before


def test_same_evidence_id_cannot_attest_different_companies():
    rows = [candidate("Acme"), candidate("Other")]
    for row in rows:
        row["discovery_evidence_ids"] = ["source:page:1:Homepage"]
    result = assess({"candidates": rows})
    assert result["identity_errors"] == {"discovery_evidence_id_collision": 1}
    assert result["factory_run_recommended"] is False


def test_repeated_reference_within_one_company_is_not_collision():
    row = candidate()
    row["discovery_evidence_ids"] = ["source:125", "source:125"]
    assert assess({"candidates": [row]})["identity_errors"] == {}
