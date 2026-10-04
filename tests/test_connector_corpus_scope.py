from src.search_intelligence.connector_corpus_scope import geography_allowed, ml_readiness
from src.search_intelligence.connector_mass_census import CompanySeed, build_mass_census


def test_company_can_span_sector_and_geography_evidence():
    census = build_mass_census([
        CompanySeed("Example GmbH", "a", website="example.org", cohort="TECH", geography="REGION_HANNOVER"),
        CompanySeed("Example GmbH", "b", website="example.org", cohort="SOCIAL", geography="REGION_HANNOVER"),
        CompanySeed("Example GmbH", "c", website="example.org", cohort="TECH", geography="BERLIN"),
    ])
    assert census["candidates"][0]["cohorts"] == ["SOCIAL", "TECH"]
    assert census["candidates"][0]["geographies"] == ["BERLIN", "REGION_HANNOVER"]


def test_social_is_hannover_only_but_tech_is_multi_region():
    assert geography_allowed("SOCIAL", "REGION_HANNOVER")
    assert not geography_allowed("SOCIAL", "BERLIN")
    assert geography_allowed("TECH", "BERLIN")
    assert geography_allowed("TECH", "MUNICH")


def test_ml_readiness_requires_positive_negative_diverse_multi_region_corpus():
    result = ml_readiness({
        "structural_fingerprint_count": 50,
        "negative_or_gap_example_count": 250,
        "success_example_count": 250,
        "geography_count": 6,
    })
    assert result["ready"] is True
