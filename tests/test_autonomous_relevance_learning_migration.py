from __future__ import annotations

from pathlib import Path


MIGRATION = Path("db/migrations/063_create_autonomous_relevance_learning.sql")


def test_autonomous_relevance_learning_tables_are_created() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS employer_origin_job_detail_evidence" in sql
    assert "CREATE TABLE IF NOT EXISTS employer_origin_learned_relevance_signals" in sql
    assert "human-provided urls are not modeled" in sql.lower()


def test_autonomous_relevance_learning_persists_signal_strengths() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "signal_type IN ('profile', 'target_location', 'remote_or_germany', 'flexibility', 'job_detail_path_pattern')" in sql
    assert "signal_strength IN ('strong', 'medium', 'weak')" in sql
    assert "relevance_decision IN ('relevant', 'insufficient_evidence', 'not_relevant')" in sql
