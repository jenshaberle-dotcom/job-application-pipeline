from src.search_intelligence.connector_mass_census import (
    CompanySeed,
    build_mass_census,
    canonical_website,
)


def test_mass_census_prefers_domain_identity_and_preserves_provenance():
    result = build_mass_census(
        [
            CompanySeed(
                "Acme GmbH", "directory-a", "https://www.acme.example/jobs", "Hannover", "IT", "1"
            ),
            CompanySeed("ACME", "directory-b", "acme.example", "Hannover", "Software", "x"),
            CompanySeed("Other Tech AG", "directory-a", None, "Garbsen", "Automation", "2"),
        ]
    )
    assert result["summary"]["raw_seed_count"] == 3
    assert result["summary"]["unique_company_count"] == 2
    assert result["summary"]["duplicate_seed_count"] == 1
    acme = next(row for row in result["candidates"] if row["websites"] == ["https://acme.example"])
    assert acme["websites"] == ["https://acme.example"]
    assert acme["seed_sources"] == ["directory-a", "directory-b"]
    assert acme["disposition"] == "ORIGIN_DISCOVERY_REQUIRED"
    assert result["boundaries"]["production_source_activation"] is False


def test_invalid_website_falls_back_without_granting_authority():
    assert canonical_website("not a host") is None
    result = build_mass_census([CompanySeed("Example GmbH", "seed")])
    assert result["candidates"][0]["websites"] == []
    assert result["boundaries"]["database_writes"] is False
