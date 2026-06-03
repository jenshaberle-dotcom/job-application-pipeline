from pathlib import Path


MIGRATION_PATH = Path("db/migrations/051_activate_enercity_discovery_source_target.sql")


def test_enercity_activation_migration_matches_current_schema() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    compact_sql = " ".join(sql.split())

    assert "source_name = 'enercity:discovery'" in sql
    assert "enercity_discovery_hannover_precision" in sql
    assert "INSERT INTO search_profiles" in sql
    assert "INSERT INTO search_terms (search_profile_id, search_term, is_active)" in sql

    assert "'full_time'" not in sql
    assert "insert into search_terms (profile_id" not in compact_sql.lower()
    assert "existing.profile_id" not in compact_sql.lower()

    assert "offer_type" in sql
    assert "1," in sql
    assert "page_size" in sql
    assert "3," in sql
    assert "true" in sql.lower()


def test_enercity_activation_migration_keeps_controlled_boundary() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "does not run ingestion" in sql
    assert "write Bronze records" in sql
    assert "scheduler changes" in sql
    assert "activate a source family" in sql
    assert "CSV/Excel/export artifacts" in sql
