from pathlib import Path


def test_stepstone_company_discovery_cycle_migration_defines_temporary_company_cooldowns() -> None:
    sql = Path("db/migrations/072_create_stepstone_company_discovery_cycle.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS search_term_cycle_state" in sql
    assert "CREATE TABLE IF NOT EXISTS company_discovery_cooldowns" in sql
    assert "CREATE TABLE IF NOT EXISTS stepstone_company_discovery_cycle_reviews" in sql
    assert "CREATE TABLE IF NOT EXISTS stepstone_company_discovery_cycle_items" in sql
    assert "temporarily cooled down" in sql
    assert "not permanently blacklisted" in sql
    assert "no automatic candidate creation" in sql
    assert "no scheduler mutation" in sql
    assert "cooldown_until" in sql
    assert "is_not_exclusion_enabled" in sql
