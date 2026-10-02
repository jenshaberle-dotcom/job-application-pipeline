from pathlib import Path

from src.search_intelligence.market_sensor_controlled_activation import (
    EXPECTED_BA_REMOTE_TERMS,
)


MIGRATION = Path(
    "db/migrations/116_expand_product_owner_system_engineer_market_coverage.sql"
)

TARGET_PROFILES = (
    "ba_data_engineer_30629_50km",
    "ba_data_engineering_remote_nationwide_review",
    "stepstone_data_engineer_hannover",
)

ADJACENT_ROLE_TERMS = (
    "Product Owner",
    "Technical Product Owner",
    "Productowner",
    "System Engineer",
    "Systems Engineer",
    "Systemingenieur",
    "IT System Engineer",
    "IT-Systemingenieur",
)


def test_adjacent_role_migration_expands_only_existing_market_sensor_profiles() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    for profile in TARGET_PROFILES:
        assert f"('{profile}')" in text

    for term in ADJACENT_ROLE_TERMS:
        assert f"('{term}')" in text

    assert "employer_origin_source_candidates" not in text
    assert "INSERT INTO search_profiles" not in text
    assert "UPDATE search_profiles" not in text


def test_ba_remote_contract_knows_new_adjacent_role_terms() -> None:
    for term in ADJACENT_ROLE_TERMS:
        assert term in EXPECTED_BA_REMOTE_TERMS
