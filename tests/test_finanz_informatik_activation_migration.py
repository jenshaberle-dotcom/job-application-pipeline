from __future__ import annotations

from pathlib import Path


MIGRATION_PATH = Path("db/migrations/022_activate_finanz_informatik_hannover_source_target.sql")


def test_finanz_informatik_activation_migration_matches_current_schema() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    compact_sql = " ".join(sql.split())

    assert "source_name = 'finanz_informatik:hannover'" in sql
    assert "insert into search_profiles" in compact_sql.lower()
    assert "insert into search_terms (search_profile_id, search_term, is_active)" in compact_sql.lower()

    assert "'full_time'" not in sql
    assert "insert into search_terms (profile_id" not in compact_sql.lower()
    assert "existing.profile_id" not in compact_sql.lower()

    # search_profiles.offer_type is currently integer-coded. This catches the
    # previous string-literal bug before it reaches a live database migration.
    assert "offer_type" in sql
    assert " 1," in sql
