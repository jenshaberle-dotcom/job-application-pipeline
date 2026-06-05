from __future__ import annotations

from pathlib import Path

MIGRATION = Path("db/migrations/064_create_adaptive_origin_job_observation.sql")


def test_adaptive_observation_migration_creates_learning_input_tables() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS origin_job_observation_runs" in sql
    assert "CREATE TABLE IF NOT EXISTS origin_job_page_observations" in sql
    assert "CREATE TABLE IF NOT EXISTS origin_observed_pattern_candidates" in sql
    assert "CREATE TABLE IF NOT EXISTS employer_origin_reprocess_benchmarks" in sql


def test_adaptive_observation_migration_declares_pipeline_boundaries() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert '"learning_input_only": true' in sql
    assert '"no_gate_decision": true' in sql
    assert '"no_candidate_status_mutation": true' in sql
    assert '"no_bronze_write": true' in sql
    assert '"no_silver_write": true' in sql
    assert '"adaptive_stop_or_extend": true' in sql


def test_adaptive_observation_migration_tracks_skipped_known_seed_inputs() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "skipped_duplicate_url_count" in sql
    assert "skipped_known_url_count" in sql
    assert "skipped_saturated_host_count" in sql
