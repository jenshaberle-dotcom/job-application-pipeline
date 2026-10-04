from src.connectors.aggressive_factory import advance_population

CATALOG = {
    "schema_version": "jap.connector_capability_catalog.v1",
    "capabilities": [{
        "capability_id": "structured_jobposting_v1",
        "version": 1,
        "roles": ["origin_inventory", "job_detail"],
        "reuse_tier": "GENERIC_ORIGIN",
        "required_fingerprint_tags": ["structured_jobposting_inventory", "structured_jobposting_detail"],
        "priority": 20,
        "enabled": True,
        "runtime_strategy": "JSONLD",
    }],
}


def test_aggressive_policy_advances_all_candidates_without_activation():
    result = advance_population([
        {
            "company_key": "alpha",
            "origin_url": "https://alpha.example/jobs",
            "source_type": "employer_origin_career_site",
            "fingerprint_tags": ["structured_jobposting_inventory", "structured_jobposting_detail"],
            "evidence_ids": ["capture:alpha"],
            "market_sensor_only": False,
        },
        {
            "company_key": "beta",
            "origin_url": "https://beta.example/jobs",
            "source_type": "employer_origin_career_site",
            "fingerprint_tags": ["unknown_structure"],
            "evidence_ids": ["capture:beta"],
            "market_sensor_only": False,
        },
        {
            "company_key": "gamma",
            "origin_url": "https://gamma.example/jobs",
            "source_type": "employer_origin_career_site",
            "fingerprint_tags": [],
            "evidence_ids": [],
            "market_sensor_only": False,
        },
    ], catalog_payload=CATALOG, census_digest="a" * 64)

    assert result["candidate_count"] == 3
    assert result["disposition_counts"] == {
        "capability_gap": 1,
        "evidence_gap": 1,
        "qualified_inactive": 1,
    }
    alpha = next(v for v in result["candidates"] if v["company_key"] == "alpha")
    assert alpha["definition_status"] == "PASS"
    assert alpha["production_activated"] is False
    assert alpha["runtime_admitted"] is False
    assert alpha["employer_specific_code_required"] is False
    beta = next(v for v in result["candidates"] if v["company_key"] == "beta")
    assert beta["engineering_gap"]["missing_roles"] == ["job_detail", "origin_inventory"]
    assert result["engineering_gap_groups"]


def test_market_sensor_does_not_become_employer_source_authority():
    result = advance_population([{
        "company_key": "sensor-only",
        "origin_url": "https://sensor.example/jobs",
        "source_type": "employer_origin_career_site",
        "fingerprint_tags": ["structured_jobposting_inventory", "structured_jobposting_detail"],
        "evidence_ids": ["sensor:1"],
        "market_sensor_only": True,
    }], catalog_payload=CATALOG, census_digest="b" * 64)
    assert result["candidates"][0]["factory_disposition"] == "evidence_gap"
    assert result["candidates"][0]["reason"] == "market_sensor_not_employer_source_authority"
