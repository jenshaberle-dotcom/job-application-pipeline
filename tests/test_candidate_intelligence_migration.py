from __future__ import annotations

from pathlib import Path


def test_candidate_intelligence_migration_creates_profile_and_skill_tables() -> None:
    migration = Path("db/migrations/032_create_candidate_intelligence_foundation.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS candidate_profiles" in migration
    assert "CREATE TABLE IF NOT EXISTS candidate_skills" in migration
    assert "UNIQUE (profile_name, profile_version)" in migration
    assert "REFERENCES candidate_profiles(id) ON DELETE CASCADE" in migration
    assert "capability_score BETWEEN 0 AND 100" in migration
    assert "career_direction_weight BETWEEN 0 AND 100" in migration


def test_candidate_intelligence_migration_documents_safety_boundary() -> None:
    migration = Path("db/migrations/032_create_candidate_intelligence_foundation.sql").read_text(encoding="utf-8")

    assert "no search-profile mutation" in migration
    assert "no source activation" in migration
    assert "no Bronze writes" in migration
