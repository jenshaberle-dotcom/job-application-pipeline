from src.search_intelligence.connector_corpus_scope import expansion_required
from src.search_intelligence.connector_mass_census import CompanySeed, build_mass_census


def test_company_can_span_sector_and_geography_evidence():
    census = build_mass_census([
        CompanySeed("Example GmbH", "a", website="example.org", cohort="TECH", geography="REGION_HANNOVER"),
        CompanySeed("Example GmbH", "b", website="example.org", cohort="SOCIAL", geography="REGION_HANNOVER"),
    ])
    assert census["candidates"][0]["cohorts"] == ["SOCIAL", "TECH"]
    assert census["candidates"][0]["geographies"] == ["REGION_HANNOVER"]


def test_ml_expansion_requires_volume_diversity_and_negative_examples():
    assert expansion_required({
        "unique_company_count": 1499,
        "structural_fingerprint_count": 100,
        "negative_or_gap_example_count": 500,
    })
    assert not expansion_required({
        "unique_company_count": 1500,
        "structural_fingerprint_count": 50,
        "negative_or_gap_example_count": 250,
    })
