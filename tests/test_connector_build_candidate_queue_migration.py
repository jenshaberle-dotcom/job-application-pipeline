from pathlib import Path


MIGRATION = Path("db/migrations/045_create_connector_build_candidate_queue.sql")
SCRIPT = Path("scripts/preview_connector_build_candidate_queue.py")
DOC = Path("docs/archive/source-analysis/connector_build_candidate_queue.md")


def test_connector_build_candidate_queue_migration_exists() -> None:
    assert MIGRATION.exists()
    text = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace view gold_connector_build_candidate_queue" in text
    assert "drop view if exists gold_connector_build_queue_summary" in text
    assert "create view gold_connector_build_queue_summary" in text
    assert "monitor_existing_source_count" in text
    assert "connector_feasibility_review_items" in text
    assert "gold_candidate_lifecycle_status" in text
    assert "build_candidate_recommended" in text
    assert "origin_url_repair_required" in text
    assert "sample_job_review_required" in text
    assert "origin_source_discovery_required" in text
    assert "continue_existing_build_flow" in text
    assert "monitor_existing_source" in text
    assert "csv" not in text.lower()


def test_connector_build_queue_preserves_read_only_boundary() -> None:
    text = MIGRATION.read_text(encoding="utf-8").lower()

    assert "insert into" not in text
    assert "update " not in text
    assert "delete from" not in text
    assert "drop table" not in text
    assert "create or replace view" in text


def test_connector_build_queue_preview_script_is_read_only_and_uses_shared_config() -> None:
    assert SCRIPT.exists()
    text = SCRIPT.read_text(encoding="utf-8")
    lowered = text.lower()

    assert "from src.config import get_database_config" in text
    assert "gold_connector_build_queue_summary" in text
    assert "gold_connector_build_candidate_queue" in text
    assert "insert " not in lowered
    assert "update " not in lowered
    assert "delete " not in lowered
    assert "--write" not in text


def test_connector_build_candidate_queue_documentation_exists() -> None:
    assert DOC.exists()
    text = DOC.read_text(encoding="utf-8")

    assert "S7O" in text
    assert "Connector Build Candidate Selection" in text
    assert "build_candidate_recommended" in text
    assert "origin_url_repair_required" in text
    assert "sample_job_review_required" in text
    assert "approval gate" in text.lower()
