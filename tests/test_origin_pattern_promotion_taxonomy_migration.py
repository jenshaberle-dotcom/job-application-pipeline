from __future__ import annotations

from pathlib import Path


def test_origin_pattern_promotion_taxonomy_migration_adds_semantic_columns() -> None:
    sql = Path("db/migrations/066_harden_origin_pattern_promotion_taxonomy.sql").read_text()

    assert "ADD COLUMN IF NOT EXISTS pattern_category" in sql
    assert "ADD COLUMN IF NOT EXISTS usage_scope" in sql
    assert "location_multi_signal" in sql
    assert "remote_work_signal" in sql
    assert "profile_ambiguous_signal" in sql
    assert "detail_url_discovery" in sql
    assert "listing_url_discovery" in sql


def test_origin_pattern_promotion_taxonomy_migration_repairs_flat_a2d_outputs() -> None:
    sql = Path("db/migrations/066_harden_origin_pattern_promotion_taxonomy.sql").read_text().lower()

    assert "pattern_type = 'remote_signal'" in sql
    assert "'+ weitere'" in sql
    assert "promotion_status = 'candidate'" in sql
    assert "pattern_type = 'profile_signal'" in sql
    assert "lower(pattern_value) = 'bi'" in sql
