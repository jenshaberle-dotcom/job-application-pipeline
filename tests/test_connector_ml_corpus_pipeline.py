from scripts.materialize_connector_ml_corpus import materialize
from scripts.evaluate_connector_factory_corpus import evaluate


def test_ml_examples_preserve_geography_cohort_and_failure_label():
    census = {
        "population_digest": "a" * 64,
        "candidates": [
            {
                "company_key": "acme",
                "geographies": ["BERLIN"],
                "cohorts": ["TECH"],
                "seed_sources": ["directory"],
            }
        ],
    }
    evaluation = {
        "candidates": [
            {
                "company_key": "acme",
                "factory_disposition": "capability_gap",
                "fingerprint_tags": ["novel"],
                "engineering_gap": {"fingerprint": "f" * 64},
            }
        ]
    }
    result = materialize(census, evaluation)
    row = result["examples"][0]
    assert row["label"] == "CAPABILITY_GAP"
    assert row["geographies"] == ["BERLIN"]
    assert row["cohorts"] == ["TECH"]
    assert row["raw_capture_persisted"] is False
    assert len(row["example_id"]) == 64


def test_factory_bridge_keeps_population_even_without_evidence():
    census = {"population_digest": "b" * 64, "candidates": [{"company_key": "missing"}]}
    result = evaluate(
        census,
        {"candidates": []},
        {"schema_version": "jap.connector_capability_catalog.v1", "capabilities": []},
    )
    assert result["candidate_count"] == 1
    assert result["disposition_counts"] == {"evidence_gap": 1}
    assert result["origin_evidence_coverage"]["missing_evidence"] == 1
